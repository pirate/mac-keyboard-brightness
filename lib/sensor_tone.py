"""Shared helpers for SPU sensor commands that emit tone streams or JSONL."""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import json
import math
import os
import signal
import sys
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

import numpy as np

from signal_stream import FloatSignalWriter, install_sigpipe_default


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def clamp01(value: float) -> float:
    return clamp(float(value), 0.0, 1.0)


def normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return clamp01((float(value) - float(low)) / (float(high) - float(low)))


def require_root() -> None:
    if os.geteuid() != 0:
        prog = os.path.basename(sys.argv[0]) or "sensor"
        raise SystemExit(f"{prog}: requires root. Run with: sudo {sys.argv[0]}")


@dataclass(frozen=True)
class ToneConfig:
    sample_rate: float
    low_hz: float
    high_hz: float
    quiet: float
    loud: float


@dataclass(frozen=True)
class SensorFrame:
    level: float
    values: dict[str, float | int | str]


def add_tone_output_args(
    parser: argparse.ArgumentParser,
    *,
    default_rate: float = 24_000.0,
    default_low_hz: float = 500.0,
    default_high_hz: float = 5_000.0,
    default_quiet: float = 0.02,
    default_loud: float = 0.7,
) -> None:
    parser.add_argument(
        "--rate",
        type=float,
        default=default_rate,
        help=f"Output sample rate in Hz (default: {default_rate:g}).",
    )
    parser.add_argument(
        "--low-hz",
        type=float,
        default=default_low_hz,
        help=f"Frequency at quiet/low sensor values (default: {default_low_hz:g}).",
    )
    parser.add_argument(
        "--high-hz",
        type=float,
        default=default_high_hz,
        help=f"Frequency at loud/high sensor values (default: {default_high_hz:g}).",
    )
    parser.add_argument(
        "--low-volume",
        type=float,
        default=default_quiet,
        help=f"Amplitude at quiet/low sensor values, 0..1 (default: {default_quiet:g}).",
    )
    parser.add_argument(
        "--high-volume",
        type=float,
        default=default_loud,
        help=f"Amplitude at loud/high sensor values, 0..1 (default: {default_loud:g}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSONL sensor readings instead of an MSIG1 tone stream.",
    )


def tone_config_from_args(args: argparse.Namespace) -> ToneConfig:
    rate = float(args.rate)
    low_hz = float(args.low_hz)
    high_hz = float(args.high_hz)
    quiet = float(args.low_volume)
    loud = float(args.high_volume)

    if rate <= 0:
        raise SystemExit("--rate must be > 0")
    if low_hz <= 0 or high_hz <= 0:
        raise SystemExit("--low-hz and --high-hz must be > 0")
    if not (0.0 <= quiet <= 1.0) or not (0.0 <= loud <= 1.0):
        raise SystemExit("--low-volume and --high-volume must be in 0..1")

    if high_hz < low_hz:
        low_hz, high_hz = high_hz, low_hz
    if loud < quiet:
        quiet, loud = loud, quiet

    return ToneConfig(
        sample_rate=rate,
        low_hz=low_hz,
        high_hz=high_hz,
        quiet=quiet,
        loud=loud,
    )


class ToneMapper:
    def __init__(self, config: ToneConfig) -> None:
        self.config = config

    def map(self, level: float) -> tuple[float, float]:
        n = clamp01(level)
        freq = self.config.low_hz + (self.config.high_hz - self.config.low_hz) * n
        amp = self.config.quiet + (self.config.loud - self.config.quiet) * n
        return float(freq), float(amp)


class ToneSynth:
    def __init__(self, *, mapper: ToneMapper, sample_rate: float) -> None:
        self.mapper = mapper
        self.sample_rate = max(1.0, float(sample_rate))
        self._phase = 0.0
        self._last_freq = mapper.config.low_hz
        self._last_amp = mapper.config.quiet

    def render(self, *, level: float, frames: int) -> np.ndarray:
        n = max(1, int(frames))
        target_freq, target_amp = self.mapper.map(level)

        freq_line = np.linspace(self._last_freq, target_freq, n, dtype=np.float64)
        amp_line = np.linspace(self._last_amp, target_amp, n, dtype=np.float64)
        phase_inc = (2.0 * math.pi * freq_line) / self.sample_rate
        phase = np.cumsum(phase_inc, dtype=np.float64) + self._phase
        out = (amp_line * np.sin(phase)).astype(np.float32, copy=False)

        self._phase = float(phase[-1] % (2.0 * math.pi))
        self._last_freq = target_freq
        self._last_amp = target_amp
        return out


class SPUReportStream:
    """Low-level stream of raw HID reports from an Apple SPU usage pair."""

    def __init__(
        self,
        *,
        usage_page: int,
        usage: int,
        report_buffer_size: int = 4096,
        report_interval_us: int = 1000,
    ) -> None:
        self.usage_page = int(usage_page)
        self.usage = int(usage)
        self.report_buffer_size = max(64, int(report_buffer_size))
        self.report_interval_us = max(1, int(report_interval_us))
        self._reports: deque[tuple[float, bytes]] = deque(maxlen=8192)
        self._hid = None

        self._iokit = ctypes.cdll.LoadLibrary(ctypes.util.find_library("IOKit"))
        self._cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))

        self._k_cf_allocator_default = ctypes.c_void_p.in_dll(
            self._cf, "kCFAllocatorDefault"
        )
        self._k_cf_run_loop_default_mode = ctypes.c_void_p.in_dll(
            self._cf, "kCFRunLoopDefaultMode"
        )
        self._setup_ffi()
        self._wake_drivers()
        self._open_matching_device()

    def _setup_ffi(self) -> None:
        self._iokit.IOServiceMatching.restype = ctypes.c_void_p
        self._iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]
        self._iokit.IOServiceGetMatchingServices.restype = ctypes.c_int
        self._iokit.IOServiceGetMatchingServices.argtypes = [
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint),
        ]
        self._iokit.IOIteratorNext.restype = ctypes.c_uint
        self._iokit.IOIteratorNext.argtypes = [ctypes.c_uint]
        self._iokit.IOObjectRelease.argtypes = [ctypes.c_uint]
        self._iokit.IORegistryEntryCreateCFProperty.restype = ctypes.c_void_p
        self._iokit.IORegistryEntryCreateCFProperty.argtypes = [
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint,
        ]
        self._iokit.IORegistryEntrySetCFProperty.restype = ctypes.c_int
        self._iokit.IORegistryEntrySetCFProperty.argtypes = [
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self._iokit.IOHIDDeviceCreate.restype = ctypes.c_void_p
        self._iokit.IOHIDDeviceCreate.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        self._iokit.IOHIDDeviceOpen.restype = ctypes.c_int
        self._iokit.IOHIDDeviceOpen.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._iokit.IOHIDDeviceClose.restype = ctypes.c_int
        self._iokit.IOHIDDeviceClose.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._iokit.IOHIDDeviceRegisterInputReportCallback.restype = None
        self._iokit.IOHIDDeviceRegisterInputReportCallback.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self._iokit.IOHIDDeviceScheduleWithRunLoop.restype = None
        self._iokit.IOHIDDeviceScheduleWithRunLoop.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]

        self._cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        self._cf.CFStringCreateWithCString.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_uint32,
        ]
        self._cf.CFNumberCreate.restype = ctypes.c_void_p
        self._cf.CFNumberCreate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        self._cf.CFNumberGetValue.restype = ctypes.c_bool
        self._cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        self._cf.CFRunLoopGetCurrent.restype = ctypes.c_void_p
        self._cf.CFRunLoopRunInMode.restype = ctypes.c_int32
        self._cf.CFRunLoopRunInMode.argtypes = [
            ctypes.c_void_p,
            ctypes.c_double,
            ctypes.c_bool,
        ]

    def _cfstr(self, text: str) -> ctypes.c_void_p:
        return self._cf.CFStringCreateWithCString(None, text.encode("utf-8"), 0x08000100)

    def _cfnum32(self, value: int) -> ctypes.c_void_p:
        val = ctypes.c_int32(int(value))
        return self._cf.CFNumberCreate(None, 3, ctypes.byref(val))

    def _prop_int(self, service: int, key: str) -> int | None:
        ref = self._iokit.IORegistryEntryCreateCFProperty(service, self._cfstr(key), None, 0)
        if not ref:
            return None
        val = ctypes.c_long()
        if not self._cf.CFNumberGetValue(ref, 4, ctypes.byref(val)):
            return None
        return int(val.value)

    def _wake_drivers(self) -> None:
        matching = self._iokit.IOServiceMatching(b"AppleSPUHIDDriver")
        iterator = ctypes.c_uint()
        self._iokit.IOServiceGetMatchingServices(0, matching, ctypes.byref(iterator))
        while True:
            service = self._iokit.IOIteratorNext(iterator.value)
            if not service:
                break
            for key, value in (
                ("SensorPropertyReportingState", 1),
                ("SensorPropertyPowerState", 1),
                ("ReportInterval", self.report_interval_us),
            ):
                _ = self._iokit.IORegistryEntrySetCFProperty(
                    service,
                    self._cfstr(key),
                    self._cfnum32(value),
                )
            self._iokit.IOObjectRelease(service)

    def _open_matching_device(self) -> None:
        matching = self._iokit.IOServiceMatching(b"AppleSPUHIDDevice")
        iterator = ctypes.c_uint()
        self._iokit.IOServiceGetMatchingServices(0, matching, ctypes.byref(iterator))
        chosen_hid = None
        while True:
            service = self._iokit.IOIteratorNext(iterator.value)
            if not service:
                break
            page = self._prop_int(service, "PrimaryUsagePage") or -1
            use = self._prop_int(service, "PrimaryUsage") or -1
            if page == self.usage_page and use == self.usage:
                hid = self._iokit.IOHIDDeviceCreate(self._k_cf_allocator_default, service)
                if hid and self._iokit.IOHIDDeviceOpen(hid, 0) == 0:
                    chosen_hid = hid
                    self._iokit.IOObjectRelease(service)
                    break
            self._iokit.IOObjectRelease(service)

        if chosen_hid is None:
            raise RuntimeError(
                f"SPU sensor usage page 0x{self.usage_page:04X} usage 0x{self.usage:04X} not found"
            )

        self._hid = chosen_hid
        self._report_buffer = (ctypes.c_uint8 * self.report_buffer_size)()
        report_cb_type = ctypes.CFUNCTYPE(
            None,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_long,
        )

        def _on_report(
            _ctx: object,
            _result: int,
            _sender: object,
            _rtype: int,
            _rid: int,
            report: ctypes.POINTER(ctypes.c_uint8),
            length: int,
        ) -> None:
            n = int(length)
            if n <= 0:
                return
            self._reports.append((time.time(), bytes(report[:n])))

        self._cb_ref = report_cb_type(_on_report)
        self._iokit.IOHIDDeviceRegisterInputReportCallback(
            self._hid,
            self._report_buffer,
            self.report_buffer_size,
            self._cb_ref,
            None,
        )
        self._iokit.IOHIDDeviceScheduleWithRunLoop(
            self._hid,
            self._cf.CFRunLoopGetCurrent(),
            self._k_cf_run_loop_default_mode,
        )

    def poll(self, timeout_s: float) -> None:
        self._cf.CFRunLoopRunInMode(
            self._k_cf_run_loop_default_mode,
            max(0.0, float(timeout_s)),
            False,
        )

    def pop_reports(self) -> list[tuple[float, bytes]]:
        if not self._reports:
            return []
        out = list(self._reports)
        self._reports.clear()
        return out

    def close(self) -> None:
        if self._hid is not None:
            try:
                _ = self._iokit.IOHIDDeviceClose(self._hid, 0)
            except Exception:
                pass
            self._hid = None


ReportParser = Callable[[float, bytes], SensorFrame | None]


def run_sensor_source(
    *,
    sensor_name: str,
    stream: SPUReportStream,
    parse_report: ReportParser,
    tone: ToneConfig,
    json_mode: bool,
    initial_level: float = 0.0,
) -> int:
    install_sigpipe_default()
    running = True

    def _stop(_sig: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    mapper = ToneMapper(tone)
    level = clamp01(initial_level)

    try:
        if json_mode:
            while running:
                stream.poll(0.25)
                for ts, report in stream.pop_reports():
                    frame = parse_report(ts, report)
                    if frame is None:
                        continue
                    level = clamp01(frame.level)
                    freq_hz, amp = mapper.map(level)
                    payload: dict[str, float | int | str] = {
                        "sensor": sensor_name,
                        "time": ts,
                        "level": level,
                        "freq_hz": freq_hz,
                        "volume": amp,
                    }
                    payload.update(frame.values)
                    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
                    sys.stdout.flush()
            return 0

        writer = FloatSignalWriter.to_stdout(sample_rate=tone.sample_rate)
        synth = ToneSynth(mapper=mapper, sample_rate=tone.sample_rate)
        chunk_frames = max(64, int(round(tone.sample_rate * 0.02)))

        while running:
            stream.poll(0.01)
            for ts, report in stream.pop_reports():
                frame = parse_report(ts, report)
                if frame is None:
                    continue
                level = clamp01(frame.level)

            writer.write(synth.render(level=level, frames=chunk_frames))
            writer.flush()
        return 0
    except BrokenPipeError:
        return 0
    finally:
        stream.close()
