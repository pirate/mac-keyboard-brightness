"""Hardware helpers for keyboard/display brightness and fan commands."""


import ctypes
import ctypes.util
import os
import pwd
import shutil
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


def resolve_kbpulse_binary(start_dir: str | None = None) -> str | None:
    """Resolve KBPulse binary from lib/ locations only."""
    candidates: list[Path] = []
    if start_dir:
        base = Path(start_dir).resolve()
        if base.name == "bin" and base.parent.name == ".venv":
            base = base.parent.parent
        candidates.extend(
            [
                base / "lib" / "KBPulse",
                base.parent / "lib" / "KBPulse",
            ]
        )
    else:
        base = Path(__file__).resolve().parent.parent
    candidates.extend(
        [
            base / "lib" / "KBPulse",
            Path(sys.prefix) / "lib" / "KBPulse",
        ]
    )
    for cand in candidates:
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return str(cand)
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


def stop_kbpulse(proc: subprocess.Popen[str], fade_ms: int = 20, *, reset: bool = True) -> None:
    try:
        if reset:
            send_kbpulse_level(proc, 0.0)
        if proc.stdin:
            proc.stdin.close()
    except Exception:
        pass
    # For non-reset control mode, allow KBPulse to exit naturally on EOF.
    # Force-terminating here can cancel the final applied level.
    if not reset:
        try:
            proc.wait(timeout=max(0.2, fade_ms / 1000.0 + 0.5))
        except Exception:
            pass
        return

    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=max(0.1, fade_ms / 1000.0 + 0.2))
        except Exception:
            proc.kill()


@dataclass
class DisplayBrightnessController:
    """Set macOS display brightness using multiple backends."""

    def __post_init__(self) -> None:
        self._backend = None
        self._display_id = None
        self._ds = None
        self._service = None
        self._key = None
        self._init_displayservices_backend()
        if self._backend is None:
            self._init_iokit_backend()
        if self._backend is None and shutil.which("brightness"):
            self._backend = "brightness-cli"

    def _init_displayservices_backend(self) -> None:
        try:
            cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
            ds = ctypes.cdll.LoadLibrary(
                "/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices"
            )
        except Exception:
            return

        if not hasattr(cg, "CGMainDisplayID"):
            return
        if not hasattr(ds, "DisplayServicesGetBrightness") or not hasattr(
            ds, "DisplayServicesSetBrightness"
        ):
            return

        cg.CGMainDisplayID.restype = ctypes.c_uint32
        ds.DisplayServicesGetBrightness.argtypes = [
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_float),
        ]
        ds.DisplayServicesGetBrightness.restype = ctypes.c_int
        ds.DisplayServicesSetBrightness.argtypes = [ctypes.c_uint32, ctypes.c_float]
        ds.DisplayServicesSetBrightness.restype = ctypes.c_int

        display = cg.CGMainDisplayID()
        if display == 0:
            return

        test = ctypes.c_float()
        kr = ds.DisplayServicesGetBrightness(display, ctypes.byref(test))
        if kr != 0:
            return

        self._backend = "displayservices"
        self._display_id = display
        self._ds = ds

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

    @property
    def backend(self) -> str | None:
        return self._backend

    def get(self) -> float | None:
        if self._backend == "displayservices":
            out = ctypes.c_float()
            kr = self._ds.DisplayServicesGetBrightness(self._display_id, ctypes.byref(out))
            if kr == 0:
                return max(0.0, min(1.0, float(out.value)))
            return None
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
        if self._backend == "displayservices":
            kr = self._ds.DisplayServicesSetBrightness(self._display_id, ctypes.c_float(clamped))
            return kr == 0
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


class _SMCKeyDataVers(ctypes.Structure):
    _fields_ = [
        ("major", ctypes.c_uint8),
        ("minor", ctypes.c_uint8),
        ("build", ctypes.c_uint8),
        ("reserved", ctypes.c_uint8),
        ("release", ctypes.c_uint16),
    ]


class _SMCKeyDataPLimit(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_uint16),
        ("length", ctypes.c_uint16),
        ("cpuPLimit", ctypes.c_uint32),
        ("gpuPLimit", ctypes.c_uint32),
        ("memPLimit", ctypes.c_uint32),
    ]


class _SMCKeyDataKeyInfo(ctypes.Structure):
    _fields_ = [
        ("dataSize", ctypes.c_uint32),
        ("dataType", ctypes.c_uint32),
        ("dataAttributes", ctypes.c_uint8),
    ]


class _SMCKeyData(ctypes.Structure):
    _fields_ = [
        ("key", ctypes.c_uint32),
        ("vers", _SMCKeyDataVers),
        ("pLimitData", _SMCKeyDataPLimit),
        ("keyInfo", _SMCKeyDataKeyInfo),
        ("result", ctypes.c_uint8),
        ("status", ctypes.c_uint8),
        ("data8", ctypes.c_uint8),
        ("data32", ctypes.c_uint32),
        ("bytes", ctypes.c_uint8 * 32),
    ]


@dataclass
class FanSpeedController:
    """Set Mac fan RPM via AppleSMC private IOKit APIs (Apple Silicon)."""

    _SMC_INDEX = 2
    _SMC_READ_BYTES = 5
    _SMC_WRITE_BYTES = 6
    _SMC_READ_KEYINFO = 9

    def __del__(self) -> None:
        self._close_applesmc()

    def __post_init__(self) -> None:
        self._backend = None
        self._conn = 0
        self._iokit = None
        self._last_kr = None
        self._fan_indices: list[int] = []
        self._fan_mins: dict[int, float] = {}
        self._fan_maxs: dict[int, float] = {}
        self._open_applesmc()
        if self._conn:
            self._init_applesmc_backend()

    @staticmethod
    def _encode_fpe2_bytes(value: float) -> bytes:
        scaled = int(round(max(0.0, float(value)) * 4.0))
        scaled = max(0, min(0xFFFF, scaled))
        return scaled.to_bytes(2, byteorder="big", signed=False)

    @staticmethod
    def _decode_fpe2_bytes(data: bytes) -> float | None:
        if len(data) < 2:
            return None
        raw = int.from_bytes(data[:2], byteorder="big", signed=False)
        return float(raw) / 4.0

    @staticmethod
    def _key_to_u32(key: str) -> int:
        return int.from_bytes(key.encode("ascii"), byteorder="big", signed=False)

    @staticmethod
    def _u32_to_fourcc(val: int) -> str:
        try:
            return int(val).to_bytes(4, byteorder="big", signed=False).decode("ascii")
        except Exception:
            return ""

    def _open_applesmc(self) -> None:
        try:
            iokit = ctypes.cdll.LoadLibrary(ctypes.util.find_library("IOKit"))
            libc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("System"))
        except Exception:
            return
        try:
            task_port = ctypes.c_uint32.in_dll(libc, "mach_task_self_").value
        except Exception:
            task_port = 0

        iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]
        iokit.IOServiceMatching.restype = ctypes.c_void_p
        iokit.IOServiceGetMatchingService.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
        iokit.IOServiceGetMatchingService.restype = ctypes.c_uint32
        iokit.IOServiceOpen.argtypes = [
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
        ]
        iokit.IOServiceOpen.restype = ctypes.c_int
        iokit.IOServiceClose.argtypes = [ctypes.c_uint32]
        iokit.IOServiceClose.restype = ctypes.c_int
        iokit.IOObjectRelease.argtypes = [ctypes.c_uint32]
        iokit.IOObjectRelease.restype = ctypes.c_int
        iokit.IOConnectCallStructMethod.argtypes = [
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        iokit.IOConnectCallStructMethod.restype = ctypes.c_int

        for service_name in (b"AppleSMC", b"AppleSMCKeysEndpoint"):
            match = iokit.IOServiceMatching(service_name)
            if not match:
                continue
            service = iokit.IOServiceGetMatchingService(0, match)
            if not service:
                continue
            conn = ctypes.c_uint32(0)
            kr = iokit.IOServiceOpen(service, ctypes.c_uint32(task_port), 0, ctypes.byref(conn))
            iokit.IOObjectRelease(service)
            self._last_kr = int(kr)
            if kr == 0 and conn.value:
                self._conn = int(conn.value)
                self._iokit = iokit
                return

    def _close_applesmc(self) -> None:
        if self._conn and self._iokit is not None:
            try:
                self._iokit.IOServiceClose(ctypes.c_uint32(self._conn))
            except Exception:
                pass
        self._conn = 0

    def _smc_call(self, in_data: _SMCKeyData) -> _SMCKeyData | None:
        if not self._conn or self._iokit is None:
            return None
        out = _SMCKeyData()
        out_size = ctypes.c_size_t(ctypes.sizeof(out))
        kr = self._iokit.IOConnectCallStructMethod(
            ctypes.c_uint32(self._conn),
            ctypes.c_uint32(self._SMC_INDEX),
            ctypes.byref(in_data),
            ctypes.sizeof(in_data),
            ctypes.byref(out),
            ctypes.byref(out_size),
        )
        self._last_kr = int(kr)
        if kr != 0:
            return None
        return out

    def _read_key(self, key: str) -> tuple[str, bytes] | None:
        if len(key) != 4:
            return None
        req = _SMCKeyData()
        req.key = self._key_to_u32(key)
        req.data8 = self._SMC_READ_KEYINFO
        info = self._smc_call(req)
        if info is None:
            return None
        data_size = int(info.keyInfo.dataSize)
        if data_size <= 0 or data_size > 32:
            return None
        dtype = self._u32_to_fourcc(int(info.keyInfo.dataType))

        req = _SMCKeyData()
        req.key = self._key_to_u32(key)
        req.keyInfo.dataSize = ctypes.c_uint32(data_size)
        req.data8 = self._SMC_READ_BYTES
        val = self._smc_call(req)
        if val is None:
            return None
        data = bytes(bytearray(val.bytes)[:data_size])
        return dtype, data

    def _write_key(self, key: str, payload: bytes) -> bool:
        info = self._read_key(key)
        if info is None:
            return False
        _dtype, _ = info
        size_info = _SMCKeyData()
        size_info.key = self._key_to_u32(key)
        size_info.data8 = self._SMC_READ_KEYINFO
        key_info_out = self._smc_call(size_info)
        if key_info_out is None:
            return False
        data_size = int(key_info_out.keyInfo.dataSize)
        if data_size <= 0 or data_size > 32:
            return False

        req = _SMCKeyData()
        req.key = self._key_to_u32(key)
        req.data8 = self._SMC_WRITE_BYTES
        req.keyInfo.dataSize = ctypes.c_uint32(data_size)
        write_bytes = payload[:data_size].ljust(data_size, b"\x00")
        for i in range(data_size):
            req.bytes[i] = write_bytes[i]
        return self._smc_call(req) is not None

    def _read_rpm_key(self, key: str) -> float | None:
        record = self._read_key(key)
        if record is None:
            return None
        dtype, data = record
        if dtype == "fpe2":
            return self._decode_fpe2_bytes(data)
        if dtype == "flt " and len(data) >= 4:
            try:
                return float(struct.unpack("<f", data[:4])[0])
            except Exception:
                return None
        if dtype in {"ui16", "si16"} and len(data) >= 2:
            return float(int.from_bytes(data[:2], "big", signed=dtype == "si16"))
        if dtype in {"ui8 ", "si8 "} and len(data) >= 1:
            return float(int.from_bytes(data[:1], "big", signed=dtype == "si8 "))
        return None

    def _write_rpm_key(self, key: str, rpm: float) -> bool:
        record = self._read_key(key)
        if record is None:
            return False
        dtype, data = record
        if dtype == "fpe2" and len(data) >= 2:
            return self._write_key(key, self._encode_fpe2_bytes(rpm))
        if dtype == "flt " and len(data) >= 4:
            return self._write_key(key, struct.pack("<f", float(rpm)))
        return False

    def _write_mode_key(self, idx: int, mode: int) -> bool:
        key = f"F{idx}Md"
        record = self._read_key(key)
        if record is None:
            return False
        dtype, data = record
        size = max(1, len(data))
        if dtype in {"ui8 ", "si8 "}:
            payload = int(mode).to_bytes(1, "big", signed=False)
        elif dtype in {"ui16", "si16"}:
            payload = int(mode).to_bytes(2, "big", signed=False)
        elif dtype in {"ui32", "si32"}:
            payload = int(mode).to_bytes(4, "big", signed=False)
        else:
            payload = int(mode).to_bytes(size, "big", signed=False)
        return self._write_key(key, payload)

    def _probe_fan(self, idx: int) -> bool:
        actual = self._read_rpm_key(f"F{idx}Ac")
        if actual is None:
            return False
        mn = self._read_rpm_key(f"F{idx}Mn")
        mx = self._read_rpm_key(f"F{idx}Mx")
        min_rpm = float(mn) if mn is not None else max(800.0, float(actual) * 0.5)
        max_rpm = float(mx) if mx is not None else max(min_rpm + 600.0, float(actual) * 1.4)
        if max_rpm < min_rpm:
            min_rpm, max_rpm = max_rpm, min_rpm
        self._fan_indices.append(idx)
        self._fan_mins[idx] = min_rpm
        self._fan_maxs[idx] = max_rpm
        return True

    def _init_applesmc_backend(self) -> None:
        if not self._conn:
            return
        for idx in range(8):
            _ = self._probe_fan(idx)
        if not self._fan_indices:
            return
        self._backend = "applesmc-iokit"

    def _left_right_indices(self) -> tuple[int, int] | None:
        if not self._fan_indices:
            return None
        if len(self._fan_indices) == 1:
            return self._fan_indices[0], self._fan_indices[0]
        return self._fan_indices[0], self._fan_indices[1]

    def _clamp_rpm(self, idx: int, value: float) -> float:
        lo = self._fan_mins.get(idx, 1200.0)
        hi = self._fan_maxs.get(idx, max(lo + 800.0, 4000.0))
        if hi < lo:
            lo, hi = hi, lo
        return max(lo, min(hi, float(value)))

    @property
    def available(self) -> bool:
        return self._backend is not None

    @property
    def backend(self) -> str | None:
        return self._backend

    @property
    def diagnostic(self) -> str:
        if self._last_kr not in (None, 0):
            return f"AppleSMC kr={self._last_kr}"
        if self._backend is not None:
            return "ok"
        if self._last_kr is not None:
            return f"IOServiceOpen kr={self._last_kr}"
        return "AppleSMC service unavailable"

    @property
    def fan_count(self) -> int:
        return len(self._fan_indices)

    def limits(self) -> tuple[tuple[float, float], tuple[float, float]] | None:
        pair = self._left_right_indices()
        if pair is None:
            return None
        left, right = pair
        return (
            (self._fan_mins[left], self._fan_maxs[left]),
            (self._fan_mins[right], self._fan_maxs[right]),
        )

    def get(self) -> tuple[float, float] | None:
        pair = self._left_right_indices()
        if pair is None:
            return None
        left_idx, right_idx = pair
        left = self._read_rpm_key(f"F{left_idx}Ac")
        right = self._read_rpm_key(f"F{right_idx}Ac")
        if left is None and right is None:
            return None
        if left is None and right is not None:
            left = right
        if right is None and left is not None:
            right = left
        return float(left), float(right)

    def set(self, left_rpm: float, right_rpm: float) -> bool:
        if self._backend != "applesmc-iokit":
            return False
        pair = self._left_right_indices()
        if pair is None:
            return False
        left_idx, right_idx = pair
        if not self._write_mode_key(left_idx, 1):
            return False
        if right_idx != left_idx:
            if not self._write_mode_key(right_idx, 1):
                return False
        left = self._clamp_rpm(left_idx, left_rpm)
        right = self._clamp_rpm(right_idx, right_rpm)
        if not self._write_rpm_key(f"F{left_idx}Tg", left):
            return False
        if right_idx != left_idx:
            if not self._write_rpm_key(f"F{right_idx}Tg", right):
                return False
        return True

    def restore_auto(self) -> bool:
        if self._backend != "applesmc-iokit":
            return False
        pair = self._left_right_indices()
        if pair is None:
            return False
        left_idx, right_idx = pair
        ok = self._write_mode_key(left_idx, 0)
        if right_idx != left_idx:
            ok = self._write_mode_key(right_idx, 0) and ok
        return ok
