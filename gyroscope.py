#!/usr/bin/env python3
"""Stream fused orientation (accel+gyro) as MSIG1 tone or JSONL."""


import argparse
import json
import math
import multiprocessing
from multiprocessing import shared_memory
import signal
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
LIB_ROOT = REPO_ROOT / "lib"
for _p in (LIB_ROOT, REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lib.bootstrap import maybe_reexec_venv

maybe_reexec_venv(__file__)


class MahonyOrientation:
    """Mahony AHRS using accel + gyro. Yaw is relative without magnetometer."""

    def __init__(self) -> None:
        self._q = [1.0, 0.0, 0.0, 0.0]
        self._kp = 1.0
        self._ki = 0.05
        self._err_int = [0.0, 0.0, 0.0]
        self._init = False
        self.gyro_latest = (0.0, 0.0, 0.0)

    def process_gyro(self, gx_dps: float, gy_dps: float, gz_dps: float) -> None:
        self.gyro_latest = (float(gx_dps), float(gy_dps), float(gz_dps))

    def update_with_accel(self, ax: float, ay: float, az: float, dt: float) -> None:
        a_norm = math.sqrt(ax * ax + ay * ay + az * az)
        if a_norm < 0.3:
            return

        gx = math.radians(self.gyro_latest[0])
        gy = math.radians(self.gyro_latest[1])
        gz = math.radians(self.gyro_latest[2])

        if not self._init:
            ax_n, ay_n, az_n = ax / a_norm, ay / a_norm, az / a_norm
            pitch0 = math.atan2(-ax_n, -az_n)
            roll0 = math.atan2(ay_n, -az_n)
            cp = math.cos(pitch0 * 0.5)
            sp = math.sin(pitch0 * 0.5)
            cr = math.cos(roll0 * 0.5)
            sr = math.sin(roll0 * 0.5)
            self._q = [
                cr * cp,
                sr * cp,
                cr * sp,
                -sr * sp,
            ]
            self._init = True
            return

        qw, qx, qy, qz = self._q
        inv_norm = 1.0 / a_norm
        ax_n, ay_n, az_n = ax * inv_norm, ay * inv_norm, az * inv_norm

        vx = 2.0 * (qx * qz - qw * qy)
        vy = 2.0 * (qw * qx + qy * qz)
        vz = qw * qw - qx * qx - qy * qy + qz * qz

        ex = (ay_n * (-vz) - az_n * (-vy))
        ey = (az_n * (-vx) - ax_n * (-vz))
        ez = (ax_n * (-vy) - ay_n * (-vx))

        self._err_int[0] += self._ki * ex * dt
        self._err_int[1] += self._ki * ey * dt
        self._err_int[2] += self._ki * ez * dt

        gx += self._kp * ex + self._err_int[0]
        gy += self._kp * ey + self._err_int[1]
        gz += self._kp * ez + self._err_int[2]

        hdt = 0.5 * dt
        dw = (-qx * gx - qy * gy - qz * gz) * hdt
        dx = (qw * gx + qy * gz - qz * gy) * hdt
        dy = (qw * gy - qx * gz + qz * gx) * hdt
        dz = (qw * gz + qx * gy - qy * gx) * hdt

        qw += dw
        qx += dx
        qy += dy
        qz += dz

        n = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
        if n > 0.0:
            inv_n = 1.0 / n
            qw *= inv_n
            qx *= inv_n
            qy *= inv_n
            qz *= inv_n

        self._q = [qw, qx, qy, qz]

    def euler_deg(self) -> tuple[float, float, float]:
        qw, qx, qy, qz = self._q
        sin_r = 2.0 * (qw * qx + qy * qz)
        cos_r = 1.0 - 2.0 * (qx * qx + qy * qy)
        roll_d = math.degrees(math.atan2(sin_r, cos_r))

        sin_p = 2.0 * (qw * qy - qz * qx)
        sin_p = max(-1.0, min(1.0, sin_p))
        pitch_d = math.degrees(math.asin(sin_p))

        sin_y = 2.0 * (qw * qz + qx * qy)
        cos_y = 1.0 - 2.0 * (qy * qy + qz * qz)
        yaw_d = math.degrees(math.atan2(sin_y, cos_y))

        return roll_d, pitch_d, yaw_d


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read fused orientation and map selected axis to a tone stream."
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
        "--axis",
        choices=("roll", "pitch", "yaw"),
        default="roll",
        help="Orientation axis to map into 0..360 tone control (default: roll).",
    )
    parser.add_argument(
        "--decimate",
        type=int,
        default=8,
        help="Keep 1 in N native SPU samples (default: 8). Lower is faster/noisier.",
    )
    return parser.parse_args()


def _angle_for_axis(axis: str, roll: float, pitch: float, yaw: float) -> float:
    if axis == "pitch":
        return pitch
    if axis == "yaw":
        return yaw
    return roll


def main() -> int:
    args = parse_args()

    from lib.sensor_tone import ToneMapper, ToneSynth, require_root, tone_config_from_args
    from lib.signal_stream import FloatSignalWriter, install_sigpipe_default
    from lib.spu_sensor import SHM_SIZE, sensor_worker, shm_read_new, shm_read_new_gyro

    require_root(__file__)
    tone = tone_config_from_args(args)
    axis = str(args.axis)
    decimate = max(1, int(args.decimate))

    shm_accel = shared_memory.SharedMemory(create=True, size=SHM_SIZE)
    shm_gyro = shared_memory.SharedMemory(create=True, size=SHM_SIZE)
    for i in range(SHM_SIZE):
        shm_accel.buf[i] = 0
        shm_gyro.buf[i] = 0

    worker: multiprocessing.Process | None = None
    running = True
    last_acc_total = 0
    last_gyro_total = 0
    last_t: float | None = None

    ahrs = MahonyOrientation()
    mapper = ToneMapper(tone)
    level = 0.0

    def _stop(_sig: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    install_sigpipe_default()

    try:
        worker = multiprocessing.Process(
            target=sensor_worker,
            args=(shm_accel.name, 0, decimate, shm_gyro.name, None, None),
            daemon=True,
        )
        worker.start()

        if args.json:
            while running:
                if worker.exitcode is not None:
                    raise RuntimeError(f"sensor worker exited with code {worker.exitcode}")

                gyro_samples, last_gyro_total = shm_read_new_gyro(shm_gyro.buf, last_gyro_total)
                for gx, gy, gz in gyro_samples:
                    ahrs.process_gyro(gx, gy, gz)

                accel_samples, last_acc_total = shm_read_new(shm_accel.buf, last_acc_total)
                if not accel_samples:
                    time.sleep(0.001)
                    continue

                for ax, ay, az in accel_samples:
                    now = time.monotonic()
                    if last_t is None:
                        dt = 0.01
                    else:
                        dt = max(0.001, min(0.05, now - last_t))
                    last_t = now

                    ahrs.update_with_accel(ax, ay, az, dt)
                    roll, pitch, yaw = ahrs.euler_deg()
                    angle = _angle_for_axis(axis, roll, pitch, yaw)
                    orientation = (angle + 360.0) % 360.0
                    level = orientation / 360.0
                    freq_hz, amp = mapper.map(level)
                    gx, gy, gz = ahrs.gyro_latest

                    payload = {
                        "sensor": "gyroscope",
                        "time": time.time(),
                        "axis": axis,
                        "orientation_proxy_deg": orientation,
                        "roll_deg": roll,
                        "pitch_deg": pitch,
                        "yaw_deg": yaw,
                        "gyro_x": gx,
                        "gyro_y": gy,
                        "gyro_z": gz,
                        "accel_x": ax,
                        "accel_y": ay,
                        "accel_z": az,
                        "level": level,
                        "freq_hz": freq_hz,
                        "volume": amp,
                    }
                    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
                    sys.stdout.flush()
            return 0

        writer = FloatSignalWriter.to_stdout(sample_rate=tone.sample_rate)
        synth = ToneSynth(mapper=mapper, sample_rate=tone.sample_rate)
        chunk_frames = max(64, int(round(tone.sample_rate * 0.02)))

        while running:
            if worker.exitcode is not None:
                raise RuntimeError(f"sensor worker exited with code {worker.exitcode}")

            gyro_samples, last_gyro_total = shm_read_new_gyro(shm_gyro.buf, last_gyro_total)
            for gx, gy, gz in gyro_samples:
                ahrs.process_gyro(gx, gy, gz)

            accel_samples, last_acc_total = shm_read_new(shm_accel.buf, last_acc_total)
            for ax, ay, az in accel_samples:
                now = time.monotonic()
                if last_t is None:
                    dt = 0.01
                else:
                    dt = max(0.001, min(0.05, now - last_t))
                last_t = now

                ahrs.update_with_accel(ax, ay, az, dt)
                roll, pitch, yaw = ahrs.euler_deg()
                angle = _angle_for_axis(axis, roll, pitch, yaw)
                orientation = (angle + 360.0) % 360.0
                level = orientation / 360.0

            writer.write(synth.render(level=level, frames=chunk_frames))
            writer.flush()

        return 0

    except BrokenPipeError:
        return 0
    except RuntimeError as exc:
        print(f"gyroscope: {exc}", file=sys.stderr)
        return 1
    finally:
        if worker is not None and worker.is_alive():
            worker.terminate()
            worker.join(timeout=1.0)
            if worker.is_alive():
                worker.kill()
                worker.join(timeout=1.0)

        shm_accel.close()
        shm_gyro.close()
        try:
            shm_accel.unlink()
        except FileNotFoundError:
            pass
        try:
            shm_gyro.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
