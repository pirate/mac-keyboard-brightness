#!/usr/bin/env python3
"""Stream lid hinge angle as MSIG1 tone or JSONL."""


import argparse
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
        description="Read Apple lid angle sensor and map closed/open to a tone stream."
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
    parser.add_argument(
        "--angle-min",
        type=float,
        default=0.0,
        help="Angle treated as fully closed (default: 0).",
    )
    parser.add_argument(
        "--angle-max",
        type=float,
        default=180.0,
        help="Angle treated as fully open (default: 180).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        from lib.sensor_tone import (
            SPUReportStream,
            SensorFrame,
            clamp,
            normalize,
            require_root,
            run_sensor_source,
            tone_config_from_args,
        )
    except Exception as exc:
        raise SystemExit(f"lid-angle dependencies unavailable: {exc}") from exc

    require_root(__file__)
    tone = tone_config_from_args(args)

    angle_min = float(args.angle_min)
    angle_max = float(args.angle_max)
    if angle_max < angle_min:
        angle_min, angle_max = angle_max, angle_min
    if angle_max <= angle_min:
        raise SystemExit("--angle-min and --angle-max must span a non-zero range")

    def parse_report(_ts: float, report: bytes) -> SensorFrame | None:
        if len(report) < 3:
            return None
        report_id = int(report[0])
        if report_id != 1:
            return None
        raw_angle = int(report[1]) | ((int(report[2]) & 0x01) << 8)
        angle = float(raw_angle)
        clamped = clamp(angle, angle_min, angle_max)
        level = normalize(clamped, angle_min, angle_max)
        return SensorFrame(
            level=level,
            values={
                "angle_deg": angle,
                "angle_clamped_deg": clamped,
                "angle_min_deg": angle_min,
                "angle_max_deg": angle_max,
            },
        )

    stream = SPUReportStream(usage_page=0x0020, usage=0x008A)
    return run_sensor_source(
        sensor_name="lid-angle",
        stream=stream,
        parse_report=parse_report,
        tone=tone,
        json_mode=bool(args.json),
    )


if __name__ == "__main__":
    raise SystemExit(main())
