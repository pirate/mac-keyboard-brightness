# apple-silicon-accelerometer

A modular, pipe-able macOS hardware signal toolkit built around 10 binaries in `./bin/`.

The toolkit treats hardware signals as **mono float32 streams** over stdin/stdout so you can chain tools UNIX-style.

## quick start

```bash
git clone https://github.com/olvvier/apple-silicon-accelerometer
cd apple-silicon-accelerometer
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Run commands directly from repo root, e.g.:

```bash
./bin/accelerometer | ./bin/visualizer
```

## stream format

All streaming commands use this wire format:

- header: `MSIG1 <sample_rate_hz>\n`
- payload: little-endian float32 mono samples

Most commands can also read raw float32 with `--raw --rate <hz>`.

## binaries (10)

- `bin/accelerometer`: live Apple SPU accelerometer stream to stdout (up to 800 Hz, requires `sudo`)
- `bin/microphone`: live microphone capture to stdout (up to device-supported rates, e.g. 44.1 kHz)
- `bin/bandpass`: streaming bandpass (same cascaded HP+LP style as `motion_live.py`)
- `bin/heartbeat`: BPM/confidence estimator from incoming filtered signal (JSON lines)
- `bin/frequency-shift`: realtime best-effort frequency scaling by scalar factor
- `bin/volume-shift`: amplitude gain scalar
- `bin/keyboard-brightness`: maps signal envelope to keyboard backlight via KBPulse
- `bin/speaker`: plays incoming signal on system audio output
- `bin/screen-brightness`: maps signal envelope to display brightness
- `bin/visualizer`: terminal live waveform/level monitor

## example pipelines

Accelerometer heartbeat detection:

```bash
sudo ./bin/accelerometer | ./bin/bandpass --low 0.8 --high 3.0 | ./bin/heartbeat
```

Microphone to keyboard flash:

```bash
./bin/microphone --rate 44100 | ./bin/keyboard-brightness
```

Modular synth-style chain:

```bash
sudo ./bin/accelerometer \
  | ./bin/bandpass --low 0.8 --high 3 \
  | tee >(./bin/keyboard-brightness) \
  | ./bin/frequency-shift 1000 \
  | ./bin/volume-shift 0.8 \
  | ./bin/speaker
```

Live monitor:

```bash
./bin/microphone --rate 44100 | ./bin/visualizer
```

## kbpulse integration

`keyboard-brightness` uses vendored KBPulse (`KBPulse/bin/KBPulse`, included in this repo).

Rebuild that binary (optional):

```bash
./scripts/rebuild_kbpulse_binary.sh
```

## permissions and notes

- `accelerometer` requires root due AppleSPU HID access.
- `keyboard-brightness` and `screen-brightness` require appropriate macOS permissions and supported hardware.
- `microphone` and `speaker` require an installed `sounddevice` runtime backend (PortAudio).
- `frequency-shift` is realtime best-effort and intentionally lightweight (artifact-prone at extreme factors).

## legacy tool

`motion_live.py` is still present as a standalone detector/monitor, but the primary interface is now `./bin/*`.

## license

MIT
