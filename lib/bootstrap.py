"""Runtime bootstrap helpers for command entrypoints."""

from __future__ import annotations

import os
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
