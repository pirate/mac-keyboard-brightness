"""Hardware helpers for keyboard/display brightness commands."""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import pwd
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


def resolve_kbpulse_binary(start_dir: str | None = None) -> str | None:
    """Resolve KBPulse binary path from common local locations."""
    base = Path(start_dir or os.getcwd()).resolve()
    candidates = [
        os.environ.get("KBPULSE_BIN"),
        str(base / "KBPulse" / "bin" / "KBPulse"),
        str(base / ".localbin" / "KBPulse"),
        str(base / "KBPulse" / "build" / "Release" / "KBPulse"),
        str(base / "KBPulse" / "build" / "Debug" / "KBPulse"),
        shutil.which("KBPulse"),
        shutil.which("kbpulse"),
    ]
    for cand in candidates:
        if not cand:
            continue
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def launch_kbpulse_stdin(
    fade_ms: int = 20,
    *,
    run_as_user: bool = True,
    start_dir: str | None = None,
) -> tuple[subprocess.Popen[str] | None, str]:
    """Launch KBPulse in stdin intensity mode."""
    bin_path = resolve_kbpulse_binary(start_dir=start_dir)
    if not bin_path:
        return None, "KBPulse binary not found"

    cmd = [bin_path, "--stdin-intensity", "--fade-ms", str(max(0, int(fade_ms)))]
    sudo_user = os.environ.get("SUDO_USER")
    if run_as_user and os.geteuid() == 0 and sudo_user and sudo_user != "root":
        try:
            pwd.getpwnam(sudo_user)
            cmd = ["sudo", "-u", sudo_user] + cmd
        except KeyError:
            pass

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        return None, str(exc)

    return proc, ""


def send_kbpulse_level(proc: subprocess.Popen[str], level: float) -> bool:
    try:
        if proc.stdin is None:
            return False
        clamped = max(0.0, min(1.0, float(level)))
        proc.stdin.write(f"{clamped:.4f}\n")
        proc.stdin.flush()
        return True
    except Exception:
        return False


def stop_kbpulse(proc: subprocess.Popen[str], fade_ms: int = 20) -> None:
    try:
        send_kbpulse_level(proc, 0.0)
        if proc.stdin:
            proc.stdin.close()
    except Exception:
        pass
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=max(0.1, fade_ms / 1000.0 + 0.2))
        except Exception:
            proc.kill()


@dataclass
class DisplayBrightnessController:
    """Set macOS display brightness using IOKit; fall back to `brightness` CLI if present."""

    def __post_init__(self) -> None:
        self._backend = None
        self._service = None
        self._key = None
        self._init_iokit_backend()
        if self._backend is None and shutil.which("brightness"):
            self._backend = "brightness-cli"

    def _init_iokit_backend(self) -> None:
        try:
            cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
            cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
            iokit = ctypes.cdll.LoadLibrary(ctypes.util.find_library("IOKit"))
        except Exception:
            return

        if not hasattr(cg, "CGDisplayIOServicePort"):
            return

        cg.CGMainDisplayID.restype = ctypes.c_uint32
        cg.CGDisplayIOServicePort.argtypes = [ctypes.c_uint32]
        cg.CGDisplayIOServicePort.restype = ctypes.c_uint32

        iokit.IODisplaySetFloatParameter.argtypes = [
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_float,
        ]
        iokit.IODisplaySetFloatParameter.restype = ctypes.c_int

        iokit.IODisplayGetFloatParameter.argtypes = [
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_float),
        ]
        iokit.IODisplayGetFloatParameter.restype = ctypes.c_int

        cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        cf.CFStringCreateWithCString.restype = ctypes.c_void_p

        display = cg.CGMainDisplayID()
        service = cg.CGDisplayIOServicePort(display)
        if service == 0:
            return

        key = cf.CFStringCreateWithCString(None, b"brightness", 0x08000100)
        if not key:
            return

        self._backend = "iokit"
        self._service = service
        self._key = key
        self._iokit = iokit

    @property
    def available(self) -> bool:
        return self._backend is not None

    def get(self) -> float | None:
        if self._backend == "iokit":
            out = ctypes.c_float()
            kr = self._iokit.IODisplayGetFloatParameter(self._service, 0, self._key, ctypes.byref(out))
            if kr == 0:
                return max(0.0, min(1.0, float(out.value)))
            return None
        if self._backend == "brightness-cli":
            try:
                p = subprocess.run(["brightness", "-l"], capture_output=True, text=True, check=False)
                for line in p.stdout.splitlines():
                    if "brightness" in line:
                        val = line.strip().split()[-1]
                        return max(0.0, min(1.0, float(val)))
            except Exception:
                return None
        return None

    def set(self, level: float) -> bool:
        clamped = max(0.0, min(1.0, float(level)))
        if self._backend == "iokit":
            kr = self._iokit.IODisplaySetFloatParameter(self._service, 0, self._key, ctypes.c_float(clamped))
            return kr == 0
        if self._backend == "brightness-cli":
            try:
                subprocess.run(["brightness", str(clamped)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                return False
        return False
