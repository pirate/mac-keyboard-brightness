# Use your Mac hardware like a modular synth!

A suite of commands like `accelerometer`, `microphone`, `bandpass`, `keyboard-brightness`, `screen-brightness`, and more that can be linked together using UNIX pipes.

All tools input and output a standardized mono audio signal that represents their sensor input/output values.

## Quickstart

```bash
pip install mac-hardware-toys

### Examples

# flash your screen according to your microphone input
microphone | screen-brightness

# play a sine wave tone based on your screen lid-angle
lid-angle | speaker

# flash the keyboard according to your heartbeat (keep your wrists on palm rests)
accelerometer | metronome | keyboard-brightness

# see more detail about any given signal by piping it into visualizer
microphone | visualizer
sine 1000 | visualizer
gyroscope | tee >(speaker) | visualizer
```

![Flashing keyboard gif](https://i.imgur.com/AS6tTre.gif)
![Flashing display gif](https://i.imgur.com/cRFsoDM.gif)

<img width="1004" height="665" alt="Screenshot 2026-02-20 at 11 19 36 PM" src="https://github.com/user-attachments/assets/c30f02b1-2695-4e5f-9724-e01986ba799d" />

## Tools

### `accelerometer`

- Purpose: read Apple SPU accelerometer and emit mono signal.
- Args: `--rate <hz>` (<= 800), `--axis x|y|z|mag`, `--raw`.
- Notes: requires root; when run from a terminal it auto-prompts via `sudo`.

### `ambient-light`

- Purpose: read ambient light sensor and emit tone mapped from low light to high light.
- Default mapping: `500 Hz -> 5000 Hz` and low volume -> high volume as light goes `0% -> 100%`.
- Args: `--rate`, `--low-hz`, `--high-hz`, `--low-volume`, `--high-volume`, `--json`.
- Notes: requires root; when run from a terminal it auto-prompts via `sudo`.

### `lid-angle`

- Purpose: read lid angle sensor and emit tone mapped from lid closed to open.
- Default mapping: `500 Hz -> 5000 Hz` and low volume -> high volume as angle goes `--angle-min -> --angle-max`.
- Args: `--rate`, `--low-hz`, `--high-hz`, `--low-volume`, `--high-volume`, `--angle-min`, `--angle-max`, `--json`.
- Notes: requires root; when run from a terminal it auto-prompts via `sudo`.

### `gyroscope`

- Purpose: read fused orientation (accel+gyro, Mahony AHRS) and emit tone mapped from the selected orientation axis.
- Default mapping: `500 Hz -> 5000 Hz` and low volume -> high volume as selected axis angle maps to `0..360`.
- Args: `--rate`, `--low-hz`, `--high-hz`, `--low-volume`, `--high-volume`, `--json`, `--axis roll|pitch|yaw`, `--decimate`.
- Notes: requires root; when run from a terminal it auto-prompts via `sudo`.
  - `roll`/`pitch` are absolute to gravity; `yaw` is relative and can drift without magnetometer.

### `microphone`

- Purpose: capture mono mic signal and emit stream.
- Args: `--rate <hz>`, `--block-size <frames>`.

### `metronome [bpm]`

- Purpose: emit metronome pulses; with piped stdin it auto-detects/follows BPM.
- Args: optional `bpm`, `--rate` (fixed mode), `--pulse-ms`, `--tone-hz`, `--level`, `--accent-every`, `--accent-gain`, `--block-size`, `--count`, `--min-bpm`, `--max-bpm`, `--detect-low-hz`, `--detect-high-hz`, `--self-echo-ms`, `--follow`, `--debug`, `--raw`.

---

### `bandpass <low_hz> <high_hz>`

- Purpose: realtime cascaded high/low-pass filter.
- Args: positional cutoffs or `--low/--high`, `--chunk-bytes`, `--raw --rate`.

### `frequency-shift <factor>`

- Purpose: best-effort realtime frequency scaling, takes a scalar multiplier like 0.1~1000.
- Args: `factor`, `--chunk-bytes`, `--raw --rate`.

### `volume-shift <gain>`

- Purpose: scalar amplitude gain.
- Args: `gain`, `--chunk-bytes`, `--raw --rate`.

### `heartbeat`

- Purpose: emit BPM/confidence JSON lines from incoming signal (typically bandpassed). When piped onward, it passes the signal through on stdout and writes JSON to stderr.
- Args: `--interval`, `--window-seconds`, `--emit-final`, `--chunk-bytes`, `--raw --rate`.

---

### `speaker`

- Purpose: play incoming stream on default output device.
- Args: `--device-rate`, `--block-size`.

### `visualizer`

- Purpose: terminal waveform + level monitor.
- Args: `--fps`, `--window-seconds`, `--chunk-bytes`, `--raw --rate`.

### `keyboard-brightness`

- Purpose: beat-follow keyboard backlight control.
- Args: `--send-hz`, `--fade-ms`, `--gain`, `--attack-ms`, `--release-ms`, `--baseline-ms`, `--decay-per-s`, `--debug`, `--as-root`, `--pulse`, `--on-time`, `--off-time`, `--set`.
- Notes:
  - `--set=<0..100>` without `--pulse` sets brightness and exits immediately (ignores stdin).
  - `--pulse=<N>` ignores stdin and pulses N times; `--set` controls pulse max brightness.

### `screen-brightness`

- Purpose: beat-follow display brightness control.
- Args: `--send-hz`, `--min-level`, `--max-level`, `--gain`, `--attack-ms`, `--release-ms`, `--baseline-ms`, `--decay-per-s`, `--debug`, `--no-restore`, `--pulse`, `--on-time`, `--off-time`, `--set`.
- Notes:
  - `--set=<0..100>` without `--pulse` sets display brightness and exits immediately (ignores stdin).
  - `--pulse=<N>` ignores stdin and pulses N times; `--set` controls pulse max brightness.

### `fan-speed`

- Purpose: signal-follow fan RPM control (both fans in sync by default; beat-alternating optional).
- Args: `--send-hz`, `--min-rpm`, `--max-rpm`, `--min-frac`, `--max-frac`, `--pulse-depth`, `--couple`, `--alternate`, `--input-map`, `--beat-threshold`, `--beat-hold-ms`, `--gain`, `--attack-ms`, `--release-ms`, `--baseline-ms`, `--decay-per-s`, `--debug`, `--no-restore`.

---

## Example Usage

Heartbeat from accelerometer:

```bash
accelerometer | bandpass 0.8 3 | heartbeat
```

Ambient light as signal source:

```bash
ambient-light | visualizer
```

Lid angle as JSONL:

```bash
lid-angle --json
```

Gyroscope fused orientation as JSONL:

```bash
gyroscope --axis roll --json
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

Auto-follow metronome from mic input, emits a metronome tone in sync with the beat of whatever audio is playing:

```bash
microphone | metronome | speaker
```

Auto-follow metronome from accelerometer, driving keyboard pulses:

```bash
accelerometer | metronome | keyboard-brightness
```

Metronome driving keyboard pulses:

```bash
metronome 120 | keyboard-brightness
```

Heartbeat telemetry while still driving keyboard brightness:

```bash
accelerometer | heartbeat | keyboard-brightness
```

Set keyboard backlight to 100% and exit:

```bash
keyboard-brightness --set=100
```

Pulse keyboard 5 times (1.2s on / 5.5s off) at 100%:

```bash
keyboard-brightness --pulse=5 --on-time=1.2 --off-time=5.5 --set=100
```

Set screen brightness to 40% and exit:

```bash
screen-brightness --set=40
```

Pulse screen brightness 3 times:

```bash
screen-brightness --pulse=3 --on-time=1.2 --off-time=5.5 --set=100
```

Metronome driving fan pulses:

```bash
metronome 120 | fan-speed --send-hz 4 --alternate --input-map beat --min-frac 0.30 --max-frac 0.70
```

Slow sine fan sweep (sync L/R):

```bash
sine 0.1 | fan-speed
```

One source, multiple sinks:

```bash
accelerometer \
  | bandpass 0.8 3 \
  | tee >(keyboard-brightness) \
  | frequency-shift 1000 \
  | volume-shift 0.8 \
  | tee >(speaker) \
  | visualizer
```

---

## Notes

- `accelerometer` requires root (AppleSPU HID access) and will auto-reexec through `sudo` by default.
- `ambient-light`, `lid-angle`, and `gyroscope` do the same for AppleSPU HID access.
- Set `MSIG_AUTO_SUDO=0` to disable auto-reexec and only print rerun guidance on stderr.
- `microphone`/`speaker` depend on `sounddevice` + PortAudio runtime.
- Keyboard/display brightness tools need supported hardware/permissions.
- `keyboard-brightness` uses the bundled Apple Silicon KBPulse binary at `lib/KBPulse` (arm64).
- `fan-speed` uses AppleSMC private IOKit APIs on Apple Silicon; writing fan targets typically requires `sudo`.
- `frequency-shift` is intentionally lightweight and artifact-prone at extreme factors.

### Development Setup

```python
git clone https://github.com/pirate/mac-hardware-toys
cd mac-hardware-toys

uv sync
source .venv/bin/activate
```

## Stdio Audio Format

All stream tools read/write:

- header: `MSIG1 <sample_rate_hz>\n`
- payload: little-endian `float32` mono samples

Most processors also support raw float32 input via `--raw --rate <hz>`.

---

## Why?

It's fun. Here are some ideas to get started:

- make your keyboard lights flash for security alerts using [Security Growler](https://github.com/pirate/security-growler)
- make your keyboard flash right before your display is about to sleep
- make your keyboard flash on incoming email
- make your keyboard flash to the beat of music
- make your keyboard flash when your boss's iPhone comes within bluetooth range

---

## Related Projects

- https://github.com/olvvier/apple-silicon-accelerometer IOReg accelerometer reading code
- https://github.com/EthanRDoesMC/KBPulse/ keyboard brightness code for M1, M2, M3, etc. macs
- https://github.com/maxmouchet/LightKit
- https://github.com/tcr/macbook-brightness
- http://stackoverflow.com/questions/3239749/programmatically-change-mac-display-brightness
- https://web.archive.org/web/20110828210316/http://mattdanger.net:80/2008/12/adjust-mac-os-x-display-brightness-from-the-terminal/
- http://osxbook.com/book/bonus/chapter10/light/
- https://github.com/samnung/maclight/blob/master/lights_handle.cpp
- http://www.keindesign.de/stefan/Web/Sites/iWeb/Site/iSpazz.html the OG
- https://github.com/bhoeting/DiscoKeyboard
