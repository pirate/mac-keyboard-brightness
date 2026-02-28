#!/usr/bin/env python3
"""Capture default microphone and stream MSIG1 float32 mono."""


import argparse
import queue
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd

REPO_ROOT = Path(__file__).resolve().parent
LIB_ROOT = REPO_ROOT / "lib"
for _p in reversed((LIB_ROOT, REPO_ROOT)):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lib.bootstrap import maybe_reexec_venv

maybe_reexec_venv(__file__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture mono float32 from default microphone and write MSIG1 stream."
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio devices and exit.",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Input device index or name substring (default: system default input).",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=None,
        help="Capture sample rate in Hz (default: input device default).",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=512,
        help="Audio callback block size in frames.",
    )
    return parser.parse_args()


def _parse_device_token(token: str | None) -> object:
    if token is None:
        return None
    t = str(token).strip()
    if not t:
        return None
    if t.isdigit():
        return int(t)
    return t


def resolve_input_rate(sd: object, requested: float | None, device: object) -> float:
    if requested is not None:
        if requested <= 0:
            raise SystemExit("--rate must be > 0")
        return float(requested)
    info = sd.query_devices(device, "input")
    rate = float(info.get("default_samplerate", 0.0) or 0.0)
    if rate <= 0:
        return 48000.0
    return rate


def main() -> int:
    args = parse_args()

    from lib.signal_stream import FloatSignalWriter

    if args.list_devices:
        print(sd.query_devices())
        return 0

    device = _parse_device_token(args.device)
    rate = resolve_input_rate(sd, args.rate, device)
    q: queue.Queue[np.ndarray] = queue.Queue(maxsize=32)
    writer = FloatSignalWriter.to_stdout(sample_rate=rate)

    def callback(indata: np.ndarray, frames: int, _time: object, _status: object) -> None:
        if frames <= 0:
            return
        mono = np.asarray(indata[:, 0], dtype=np.float32).copy()
        try:
            q.put_nowait(mono)
        except queue.Full:
            try:
                _ = q.get_nowait()
            except queue.Empty:
                pass
            try:
                q.put_nowait(mono)
            except queue.Full:
                pass

    try:
        with sd.InputStream(
            device=device,
            channels=1,
            samplerate=rate,
            dtype="float32",
            blocksize=max(1, int(args.block_size)),
            callback=callback,
        ):
            while True:
                chunk = q.get()
                writer.write(chunk)
                writer.flush()
    except KeyboardInterrupt:
        return 0
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
