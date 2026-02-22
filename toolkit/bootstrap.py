"""Runtime bootstrap helpers for bin command entrypoints."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def maybe_reexec_venv(script_path: str, *, env_flag: str = "MSIG_SKIP_REEXEC") -> None:
    """Re-exec into ./.venv/bin/python when available.

    This lets ./bin scripts work without manually activating the venv.
    """
    debug = os.environ.get("MSIG_DEBUG_REEXEC") == "1"
    if os.environ.get(env_flag) == "1":
        if debug:
            print(f"[msig] skip reexec via {env_flag}=1", file=sys.stderr)
        return

    script = Path(script_path).resolve()
    repo_root = script.parents[1]
    vpy = repo_root / ".venv" / "bin" / "python"
    if not vpy.exists():
        if debug:
            print(f"[msig] no venv python at {vpy}", file=sys.stderr)
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
