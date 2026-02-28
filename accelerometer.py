#!/usr/bin/env python3
"""Stream Apple SPU accelerometer as MSIG1 float32 mono."""


import argparse
import math
import multiprocessing
from multiprocessing import shared_memory
import os
import signal
import stat
import struct
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
LIB_ROOT = REPO_ROOT / "lib"
for _p in reversed((LIB_ROOT, REPO_ROOT)):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lib.bootstrap import maybe_reexec_venv, require_root

maybe_reexec_venv(__file__)

NATIVE_RATE_HZ = 800.0
DEBUG_ACCEL = os.environ.get("MSIG_DEBUG_ACCEL") == "1"
PAYLOAD_FLUSH_BYTES = 4096
PAYLOAD_FLUSH_SECONDS = 0.05


def _debug(msg: str) -> None:
    if DEBUG_ACCEL:
        print(f"[accelerometer] {msg}", file=sys.stderr, flush=True)


def _fd_kind(fd: int) -> str:
    mode = os.fstat(fd).st_mode
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISCHR(mode):
        return "char"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISSOCK(mode):
        return "sock"
    return "other"


class LinearResampler:
    """Minimal streaming linear resampler without external deps."""

    def __init__(self, input_rate: float, output_rate: float) -> None:
        if input_rate <= 0 or output_rate <= 0:
            raise ValueError("sample rates must be > 0")
        self.step = float(input_rate) / float(output_rate)
        self.buf: list[float] = []
        self.pos = 0.0

    def process(self, samples: list[float]) -> list[float]:
        if samples:
            self.buf.extend(float(s) for s in samples)
        if len(self.buf) < 2:
            return []

        out: list[float] = []
        max_pos = len(self.buf) - 1
        while self.pos < max_pos:
            i = int(self.pos)
            frac = self.pos - i
            a = self.buf[i]
            b = self.buf[i + 1]
            out.append(a + (b - a) * frac)
            self.pos += self.step

        trim = int(self.pos)
        if trim > 0:
            self.buf = self.buf[trim:]
            self.pos -= trim
        return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read Apple SPU accelerometer and write MSIG1 float32 mono to stdout."
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=800.0,
        help="Target output sample rate in Hz (0 < rate <= 800).",
    )
    parser.add_argument(
        "--axis",
        choices=("x", "y", "z", "mag"),
        default="mag",
        help="Axis to output as mono signal (default: mag).",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Emit raw float32 payload without MSIG1 header.",
    )
    return parser.parse_args()


def extract_axis(samples: list[tuple[float, float, float]], axis: str) -> list[float]:
    if axis == "x":
        return [x for x, _, _ in samples]
    if axis == "y":
        return [y for _, y, _ in samples]
    if axis == "z":
        return [z for _, _, z in samples]
    return [math.sqrt(x * x + y * y + z * z) for x, y, z in samples]


def write_header(sample_rate: float) -> None:
    payload = f"MSIG1 {int(round(sample_rate))}\n".encode("ascii")
    _write_all(payload)


def _write_all(payload: bytes) -> None:
    fd = 1
    view = memoryview(payload)
    while view:
        n = os.write(fd, view)
        if n <= 0:
            raise RuntimeError("stdout write returned <= 0")
        view = view[n:]


def main() -> int:
    _debug("start")
    _debug(f"stdout fd1: isatty={os.isatty(1)} kind={_fd_kind(1)}")
    try:
        sofd = sys.stdout.fileno()
        _debug(f"sys.stdout.fileno={sofd} kind={_fd_kind(sofd)}")
    except Exception as exc:
        _debug(f"sys.stdout.fileno unavailable: {exc}")
    args = parse_args()
    _debug("parsed args")
    if args.rate <= 0 or args.rate > NATIVE_RATE_HZ:
        raise SystemExit("--rate must satisfy: 0 < rate <= 800")

    require_root(__file__)
    _debug("root ok")

    # Emit stream metadata before lower-level sensor setup so downstream
    # pipeline tools can validate format immediately.
    if not args.raw:
        try:
            write_header(float(args.rate))
        except BrokenPipeError:
            return 0
        _debug("header written")

    from lib.spu_sensor import SHM_SIZE, sensor_worker, shm_read_new
    _debug("spu_sensor imported")

    decimate = max(1, int(math.floor(NATIVE_RATE_HZ / float(args.rate))))
    worker_rate = NATIVE_RATE_HZ / float(decimate)
    resampler = (
        LinearResampler(worker_rate, float(args.rate))
        if abs(worker_rate - args.rate) > 1e-6
        else None
    )

    shm = shared_memory.SharedMemory(create=True, size=SHM_SIZE)
    _debug("shared memory allocated")
    for i in range(SHM_SIZE):
        shm.buf[i] = 0
    worker: multiprocessing.Process | None = None
    last_total = 0
    running = True
    payload_buf = bytearray()
    last_flush = time.monotonic()

    def _stop(_sig: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    try:
        worker = multiprocessing.Process(
            target=sensor_worker,
            args=(shm.name, 0, decimate),
            daemon=True,
        )
        worker.start()
        _debug("sensor worker started")

        while running:
            if worker.exitcode is not None:
                raise RuntimeError(f"sensor worker exited with code {worker.exitcode}")

            samples, last_total = shm_read_new(shm.buf, last_total)
            if not samples:
                time.sleep(0.001)
                continue

            mono = extract_axis(samples, args.axis)
            out = resampler.process(mono) if resampler is not None else mono
            if out:
                payload_buf.extend(struct.pack("<%sf" % len(out), *out))
                now = time.monotonic()
                if (
                    len(payload_buf) >= PAYLOAD_FLUSH_BYTES
                    or (now - last_flush) >= PAYLOAD_FLUSH_SECONDS
                ):
                    _write_all(payload_buf)
                    payload_buf.clear()
                    last_flush = now

    except BrokenPipeError:
        pass
    except RuntimeError as exc:
        print(f"accelerometer: {exc}", file=sys.stderr)
        return 1
    finally:
        if payload_buf:
            try:
                _write_all(payload_buf)
            except BrokenPipeError:
                pass
        if worker is not None and worker.is_alive():
            worker.terminate()
            worker.join(timeout=1.0)
            if worker.is_alive():
                worker.kill()
                worker.join(timeout=1.0)
        shm.close()
        try:
            shm.unlink()
        except FileNotFoundError:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
