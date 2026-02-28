"""Runtime bootstrap helpers for command entrypoints."""


import os
import shutil
import shlex
import subprocess
import sys
from pathlib import Path


def maybe_reexec_venv(script_path: str, *, env_flag: str = "MSIG_SKIP_REEXEC") -> None:
    """Re-exec into ./.venv/bin/python when available.

    This lets commands work without manually activating the venv.
    """
    debug = os.environ.get("MSIG_DEBUG_REEXEC") == "1"
    if os.environ.get(env_flag) == "1":
        if debug:
            print(f"[msig] skip reexec via {env_flag}=1", file=sys.stderr)
        return

    script = Path(script_path).resolve()
    candidates = [script.parent]
    if len(script.parents) >= 2:
        candidates.append(script.parents[1])

    vpy = None
    for base in candidates:
        cand = base / ".venv" / "bin" / "python"
        if cand.exists():
            vpy = cand
            break

    if vpy is None:
        if debug:
            print(f"[msig] no venv python found for {script}", file=sys.stderr)
        return

    try:
        cur = Path(sys.executable)
    except Exception:
        cur = Path(sys.executable)

    same = False
    try:
        same = os.path.samefile(cur, vpy)
    except Exception:
        same = str(cur) == str(vpy)

    if same:
        if debug:
            print(f"[msig] already in venv python: {cur}", file=sys.stderr)
        return

    if debug:
        print(f"[msig] reexec {script} with {vpy}", file=sys.stderr)
    os.environ[env_flag] = "1"
    os.execv(str(vpy), [str(vpy), str(script), *sys.argv[1:]])


def _env_flag(name: str, *, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _resolve_script_path(script_path: str | None) -> str:
    if script_path:
        return str(Path(script_path).resolve())

    argv0 = sys.argv[0] if sys.argv else ""
    if not argv0:
        return ""
    if "/" in argv0:
        return str(Path(argv0).resolve())

    found = shutil.which(argv0)
    if found:
        return found
    return argv0


def _has_controlling_tty() -> bool:
    try:
        with open("/dev/tty", "rb"):
            return True
    except OSError:
        return False


def _sudo_hint() -> str:
    argv0 = sys.argv[0] if sys.argv else "command"
    return shlex.join(["sudo", argv0, *sys.argv[1:]])


def require_root(script_path: str | None = None, *, auto_env: str = "MSIG_AUTO_SUDO") -> None:
    """Ensure command runs as root.

    If not already root, attempt to re-exec via sudo while preserving stdio so
    pipelines continue to work. When sudo prompting is impossible, emit a
    stderr-only message with rerun guidance.
    """
    if os.geteuid() == 0:
        return

    prog = Path(sys.argv[0]).name if sys.argv else "command"
    script = _resolve_script_path(script_path)
    can_auto = _env_flag(auto_env, default=True)
    sudo_bin = shutil.which("sudo")
    has_tty = _has_controlling_tty()

    if can_auto and sudo_bin:
        cmd = [sudo_bin, "-E"]
        if not has_tty:
            # In non-interactive contexts only proceed when sudo is already cached
            # (or NOPASSWD), so we avoid noisy prompt failures on stderr.
            check = subprocess.run(
                [sudo_bin, "-n", "true"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if check.returncode != 0:
                cmd = []
            else:
                cmd.append("-n")
        if cmd:
            cmd.extend([sys.executable, script, *sys.argv[1:]])
            os.execv(sudo_bin, cmd)

    print(f"{prog}: requires root privileges.", file=sys.stderr)
    if can_auto and not has_tty:
        print(
            f"{prog}: cannot prompt for sudo password without a controlling TTY.",
            file=sys.stderr,
        )
    print(f"{prog}: rerun with: {_sudo_hint()}", file=sys.stderr)
    raise SystemExit(1)
