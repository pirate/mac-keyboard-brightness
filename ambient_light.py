#!/usr/bin/env python3
"""Stream ambient light sensor as MSIG1 tone or JSONL."""


import argparse
import math
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
LIB_ROOT = REPO_ROOT / "lib"
for _p in (LIB_ROOT, REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lib.bootstrap import maybe_reexec_venv

maybe_reexec_venv(__file__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read Apple ambient light sensor and map intensity to a tone stream."
    )
    from lib.sensor_tone import add_tone_output_args

    add_tone_output_args(
        parser,
        default_rate=24_000.0,
        default_low_hz=500.0,
        default_high_hz=5_000.0,
        default_quiet=0.02,
        default_loud=0.7,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    from lib.sensor_tone import (
        SPUReportStream,
        SensorFrame,
        clamp01,
        require_root,
        run_sensor_source,
        tone_config_from_args,
    )

    require_root(__file__)
    tone = tone_config_from_args(args)

    def parse_report(_ts: float, report: bytes) -> SensorFrame | None:
        if len(report) < 44:
            return None
        try:
            raw = float(struct.unpack_from("<f", report, 40)[0])
        except struct.error:
            return None
        if not math.isfinite(raw):
            return None
        intensity = clamp01(raw)
        return SensorFrame(
            level=intensity,
            values={
                "intensity": intensity,
                "raw_intensity": raw,
            },
        )

    stream = SPUReportStream(usage_page=0xFF00, usage=0x0004)
    return run_sensor_source(
        sensor_name="ambient-light",
        stream=stream,
        parse_report=parse_report,
        tone=tone,
        json_mode=bool(args.json),
    )


if __name__ == "__main__":
    raise SystemExit(main())
