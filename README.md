# apple-silicon-accelerometer

A modular, pipe-able macOS hardware signal toolkit with runnable commands at repo top-level.

Everything speaks one stream format so tools can be mixed freely in UNIX pipelines.

## quick start

```bash
git clone https://github.com/olvvier/apple-silicon-accelerometer
cd apple-silicon-accelerometer
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r lib/requirements.txt
export PATH="$PWD:$PATH"
```

## stream model

All stream tools read/write:

- header: `MSIG1 <sample_rate_hz>\n`
- payload: little-endian `float32` mono samples

Most processors also support raw float32 input via `--raw --rate <hz>`.

## command reference

### source commands

1. `accelerometer`
- Purpose: read Apple SPU accelerometer and emit mono signal.
- Args: `--rate <hz>` (<= 800), `--axis x|y|z|mag`, `--raw`.
- Notes: requires `sudo`.

2. `microphone`
- Purpose: capture mono mic signal and emit stream.
- Args: `--rate <hz>`, `--block-size <frames>`.

3. `metronome [bpm]`
- Purpose: emit metronome pulses; with piped stdin it auto-detects/follows BPM.
- Args: optional `bpm`, `--rate` (fixed mode), `--pulse-ms`, `--tone-hz`, `--level`, `--accent-every`, `--accent-gain`, `--block-size`, `--min-bpm`, `--max-bpm`, `--detect-low-hz`, `--detect-high-hz`, `--self-echo-ms`, `--follow`, `--debug`, `--raw`.

### processor / analysis commands

4. `bandpass <low_hz> <high_hz>`
- Purpose: realtime cascaded high/low-pass filter.
- Args: positional cutoffs or `--low/--high`, `--chunk-bytes`, `--raw --rate`.

5. `frequency-shift <factor>`
- Purpose: best-effort realtime frequency scaling.
- Args: `factor`, `--chunk-bytes`, `--raw --rate`.

6. `volume-shift <gain>`
- Purpose: scalar amplitude gain.
- Args: `gain`, `--chunk-bytes`, `--raw --rate`.

7. `heartbeat`
- Purpose: emit BPM/confidence JSON lines from incoming signal (typically bandpassed).
- Args: `--interval`, `--window-seconds`, `--emit-final`, `--chunk-bytes`, `--raw --rate`.

### output / sink commands

8. `speaker`
- Purpose: play incoming stream on default output device.
- Args: `--device-rate`, `--block-size`.

9. `visualizer`
- Purpose: terminal waveform + level monitor.
- Args: `--fps`, `--window-seconds`, `--chunk-bytes`, `--raw --rate`.

10. `keyboard-brightness`
- Purpose: beat-follow keyboard backlight control.
- Args: `--send-hz`, `--fade-ms`, `--gain`, `--attack-ms`, `--release-ms`, `--baseline-ms`, `--decay-per-s`, `--debug`, `--as-root`.
- Alias: `keyboad-brightness` (compat typo alias).

11. `screen-brightness`
- Purpose: beat-follow display brightness control.
- Args: `--send-hz`, `--min-level`, `--max-level`, `--gain`, `--attack-ms`, `--release-ms`, `--baseline-ms`, `--decay-per-s`, `--debug`, `--no-restore`.

12. `fan-speed`
- Purpose: signal-follow fan RPM control (both fans in sync by default; beat-alternating optional).
- Args: `--send-hz`, `--min-rpm`, `--max-rpm`, `--min-frac`, `--max-frac`, `--pulse-depth`, `--couple`, `--alternate`, `--input-map`, `--beat-threshold`, `--beat-hold-ms`, `--gain`, `--attack-ms`, `--release-ms`, `--baseline-ms`, `--decay-per-s`, `--debug`, `--no-restore`.

## mix-and-match recipes

Heartbeat from accelerometer:

```bash
sudo accelerometer | bandpass 0.8 3 | heartbeat
```

Music-reactive keyboard + speakers:

```bash
microphone --rate 44100 \
  | tee >(keyboard-brightness --send-hz 30 --fade-ms 20) \
  | volume-shift 0.8 \
  | speaker
```

Metronome to speakers:

```bash
metronome 120 | speaker
```

Auto-follow metronome from mic input:

```bash
microphone --rate 44100 | metronome | speaker
```

Metronome driving keyboard pulses:

```bash
metronome 120 | keyboard-brightness --send-hz 24 --fade-ms 20
```

Metronome driving fan pulses:

```bash
metronome 120 | sudo fan-speed --send-hz 4 --alternate --input-map beat --min-frac 0.30 --max-frac 0.70
```

Slow sine fan sweep (sync L/R):

```bash
sine 0.1 | sudo fan-speed
```

One source, multiple sinks:

```bash
sudo accelerometer \
  | bandpass 0.8 3 \
  | tee >(keyboard-brightness) >(visualizer) \
  | frequency-shift 1000 \
  | volume-shift 0.8 \
  | speaker
```

## practical notes

- `accelerometer` requires root (AppleSPU HID access).
- `microphone`/`speaker` depend on `sounddevice` + PortAudio runtime.
- Keyboard/display brightness tools need supported hardware/permissions.
- `fan-speed` uses AppleSMC private IOKit APIs on Apple Silicon; writing fan targets typically requires `sudo`.
- `frequency-shift` is intentionally lightweight and artifact-prone at extreme factors.

## legacy script

`motion_live.py` remains available, but primary usage is top-level commands in this repo.

## license

MIT

## links

- apple silicon accelerometer: https://github.com/olvvier/apple-silicon-accelerometer
- KBPulse: https://github.com/EthanRDoesMC/KBPulse/
