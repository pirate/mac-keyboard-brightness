"""Utilities for streaming mono float32 signals through stdin/stdout.

Protocol:
- Header line: b"MSIG1 <sample_rate>\\n"
- Payload: little-endian float32 mono samples.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import BinaryIO, Iterator, Optional

import numpy as np

MAGIC = b"MSIG1 "


class StreamFormatError(RuntimeError):
    """Raised when the input stream does not match expected format."""


@dataclass
class FloatSignalReader:
    """Incrementally read float32 mono samples from a stream."""

    stream: BinaryIO
    sample_rate: float
    carry: bytearray

    @classmethod
    def from_stdin(
        cls,
        *,
        raw: bool = False,
        sample_rate: Optional[float] = None,
    ) -> "FloatSignalReader":
        stream = sys.stdin.buffer
        rate, prefix = read_header(stream, raw=raw, sample_rate=sample_rate)
        return cls(stream=stream, sample_rate=rate, carry=bytearray(prefix))

    def iter_chunks(self, chunk_bytes: int = 16384) -> Iterator[np.ndarray]:
        """Yield chunks as float32 numpy arrays."""
        while True:
            data = self.stream.read(chunk_bytes)
            if not data:
                break
            if self.carry:
                self.carry.extend(data)
                raw = self.carry
            else:
                raw = bytearray(data)

            n_aligned = (len(raw) // 4) * 4
            if n_aligned == 0:
                self.carry = bytearray(raw)
                continue

            payload = memoryview(raw)[:n_aligned]
            out = np.frombuffer(payload, dtype="<f4").astype(np.float32, copy=False)
            yield out

            rem = raw[n_aligned:]
            self.carry = bytearray(rem)


@dataclass
class FloatSignalWriter:
    """Write float32 mono samples to stdout."""

    stream: BinaryIO
    sample_rate: float

    @classmethod
    def to_stdout(cls, *, sample_rate: float, raw: bool = False) -> "FloatSignalWriter":
        writer = cls(stream=sys.stdout.buffer, sample_rate=float(sample_rate))
        if not raw:
            writer.write_header()
        return writer

    def write_header(self) -> None:
        self.stream.write(MAGIC + f"{int(round(self.sample_rate))}\n".encode("ascii"))
        self.stream.flush()

    def write(self, samples: np.ndarray) -> None:
        arr = np.asarray(samples, dtype=np.float32)
        if arr.ndim != 1:
            arr = arr.reshape(-1)
        self.stream.write(arr.astype("<f4", copy=False).tobytes())

    def flush(self) -> None:
        self.stream.flush()


def read_header(
    stream: BinaryIO,
    *,
    raw: bool = False,
    sample_rate: Optional[float] = None,
) -> tuple[float, bytes]:
    """Read an MSIG header, or treat the stream as raw float32 data."""
    prefix = stream.read(6)
    if not prefix:
        raise EOFError("no input available")

    if prefix == MAGIC:
        rate_bytes = bytearray()
        for _ in range(20):
            ch = stream.read(1)
            if not ch:
                break
            if ch == b"\n":
                break
            rate_bytes.extend(ch)
        if not rate_bytes:
            raise StreamFormatError("missing sample rate in header")
        try:
            rate = float(rate_bytes.decode("ascii", errors="strict").strip())
        except ValueError as exc:
            raise StreamFormatError("invalid sample rate in header") from exc
        if rate <= 0:
            raise StreamFormatError("sample rate must be > 0")
        return rate, b""

    if raw:
        if sample_rate is None or sample_rate <= 0:
            raise StreamFormatError("raw mode requires --rate")
        return float(sample_rate), prefix

    raise StreamFormatError(
        "expected MSIG1 stream header; use --raw --rate <hz> for raw float32 input"
    )


def install_sigpipe_default() -> None:
    """Use default SIGPIPE behavior so broken pipes exit quietly in UNIX pipelines."""
    try:
        import signal

        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except Exception:
        pass


def read_float32_all_from_stdin_raw() -> np.ndarray:
    """Read all remaining stdin bytes as float32, dropping trailing partial sample."""
    data = sys.stdin.buffer.read()
    n_aligned = (len(data) // 4) * 4
    if n_aligned <= 0:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(data[:n_aligned], dtype="<f4").astype(np.float32, copy=False)


def is_tty_stdin() -> bool:
    return os.isatty(sys.stdin.fileno())
