"""Streaming DSP helpers used by the ./bin commands."""


import math
from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass
class CascadedBandpass:
    """Bandpass made of first-order high-pass then low-pass filters."""

    sample_rate: float
    low_hz: float
    high_hz: float

    def __post_init__(self) -> None:
        fs = float(self.sample_rate)
        if fs <= 0:
            raise ValueError("sample_rate must be > 0")
        if self.low_hz <= 0 or self.high_hz <= self.low_hz:
            raise ValueError("require 0 < low_hz < high_hz")
        self.hp_alpha = fs / (fs + 2.0 * math.pi * self.low_hz)
        self.lp_alpha = 2.0 * math.pi * self.high_hz / (2.0 * math.pi * self.high_hz + fs)
        self.hp_prev_in = 0.0
        self.hp_prev_out = 0.0
        self.lp_prev = 0.0

    def process(self, samples: np.ndarray) -> np.ndarray:
        x = np.asarray(samples, dtype=np.float32)
        if x.size == 0:
            return x
        out = np.empty_like(x)
        hp_prev_in = self.hp_prev_in
        hp_prev_out = self.hp_prev_out
        lp_prev = self.lp_prev
        hp_a = self.hp_alpha
        lp_a = self.lp_alpha
        one_minus_lp = 1.0 - lp_a

        for i, s in enumerate(x):
            hp = hp_a * (hp_prev_out + float(s) - hp_prev_in)
            hp_prev_in = float(s)
            hp_prev_out = hp
            lp = lp_a * hp + one_minus_lp * lp_prev
            lp_prev = lp
            out[i] = lp

        self.hp_prev_in = hp_prev_in
        self.hp_prev_out = hp_prev_out
        self.lp_prev = lp_prev
        return out


@dataclass
class AdaptiveLevel:
    """Adaptive envelope + decay for driving brightness-like controls."""

    noise: float = 1e-4
    peak: float = 2e-3
    decay_per_s: float = 7.0

    def __post_init__(self) -> None:
        self.level = 0.0

    def update(self, sample: float, dt: float) -> float:
        mag = abs(float(sample))
        self.noise += 0.002 * (mag - self.noise)
        if mag > self.peak:
            self.peak += 0.15 * (mag - self.peak)
        else:
            self.peak += 0.01 * (mag - self.peak)

        span = max(1e-7, self.peak - self.noise)
        norm = max(0.0, min(1.0, (mag - self.noise) / span))
        pulse = norm ** 0.65
        decay = math.exp(-self.decay_per_s * max(0.0, dt))
        self.level = max(pulse, self.level * decay)
        return self.level


@dataclass
class HeartbeatEstimator:
    """Estimate BPM using autocorrelation on recent filtered samples."""

    sample_rate: float
    window_seconds: float = 10.0

    def __post_init__(self) -> None:
        maxlen = max(64, int(self.sample_rate * self.window_seconds))
        self.buf = deque(maxlen=maxlen)

    def add(self, samples: np.ndarray) -> None:
        for s in np.asarray(samples, dtype=np.float32):
            self.buf.append(float(s))

    def estimate(self) -> tuple[float | None, float]:
        fs = self.sample_rate
        if len(self.buf) < int(fs * 5):
            return None, 0.0

        arr = np.asarray(self.buf, dtype=np.float64)
        arr -= float(arr.mean())
        var = float(np.dot(arr, arr))
        if var < 1e-20:
            return None, 0.0

        lag_lo = int(fs * 0.3)   # 200 bpm max
        lag_hi = min(int(fs * 1.2), arr.size // 2)  # 50 bpm min
        if lag_hi <= lag_lo:
            return None, 0.0

        best_r = -1.0
        best_lag = lag_lo
        for lag in range(lag_lo, lag_hi):
            a = arr[:-lag]
            b = arr[lag:]
            r = float(np.dot(a, b) / var)
            if r > best_r:
                best_r = r
                best_lag = lag

        if best_r < 0.12:
            return None, max(0.0, best_r)

        bpm = 60.0 / (best_lag / fs)
        conf = max(0.0, min(1.0, best_r))
        return bpm, conf


@dataclass
class ChunkFrequencyScaler:
    """Crude real-time frequency scaling using chunk-local periodic interpolation."""

    factor: float

    def process(self, samples: np.ndarray) -> np.ndarray:
        x = np.asarray(samples, dtype=np.float32)
        n = x.size
        if n <= 1 or self.factor == 1.0:
            return x
        base = np.arange(n, dtype=np.float64)
        idx = np.mod(base * self.factor, n - 1)
        y = np.interp(idx, base, x.astype(np.float64, copy=False))
        return y.astype(np.float32, copy=False)


@dataclass
class LinearResampler:
    """Streaming linear resampler from input rate to output rate."""

    input_rate: float
    output_rate: float

    def __post_init__(self) -> None:
        if self.input_rate <= 0 or self.output_rate <= 0:
            raise ValueError("sample rates must be > 0")
        self.step = self.input_rate / self.output_rate
        self.buffer = np.zeros(0, dtype=np.float32)
        self.pos = 0.0

    def process(self, samples: np.ndarray) -> np.ndarray:
        x = np.asarray(samples, dtype=np.float32)
        if x.size == 0:
            return np.zeros(0, dtype=np.float32)

        if self.buffer.size == 0:
            self.buffer = x.copy()
        else:
            self.buffer = np.concatenate([self.buffer, x])

        if self.buffer.size < 2:
            return np.zeros(0, dtype=np.float32)

        max_pos = self.buffer.size - 1
        if self.pos >= max_pos:
            trim = int(self.pos) - 1
            if trim > 0:
                self.buffer = self.buffer[trim:]
                self.pos -= trim
            max_pos = self.buffer.size - 1

        n_out = int((max_pos - self.pos) / self.step)
        if n_out <= 0:
            return np.zeros(0, dtype=np.float32)

        idx = self.pos + np.arange(n_out, dtype=np.float64) * self.step
        base = np.arange(self.buffer.size, dtype=np.float64)
        y = np.interp(idx, base, self.buffer.astype(np.float64, copy=False)).astype(np.float32)

        self.pos = float(idx[-1] + self.step)

        trim = int(self.pos) - 1
        if trim > 0:
            self.buffer = self.buffer[trim:]
            self.pos -= trim

        return y
