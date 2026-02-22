# Use your Mac hardware like a modular synth!

A suite of commands like `accelerometer`, `microphone`, `bandpass`, `keyboard-brightness`, `screen-brightness`, and more that can be linked together using UNIX pipes.

All tools input and output a standardized mono audio signal that represents their sensor input/output values.

## Quickstart

```bash
git clone https://github.com/olvvier/apple-silicon-accelerometer
cd apple-silicon-accelerometer

uv venv
uv sync
source .venv/bin/activate

# flash the keyboard according to your heartbeat (keep your wrists on palm rests)
sudo accelerometer \
  | bandpass 0.8 3 \
  | tee >(visualizer) \
  | metronome \
  | volume-shift 0.8 \
  | keyboard-brightness
```

![Flashing keyboard gif](https://i.imgur.com/AS6tTre.gif)
![Flashing display gif](https://i.imgur.com/cRFsoDM.gif)


<img width="1004" height="665" alt="Screenshot 2026-02-20 at 11 19 36 PM" src="https://github.com/user-attachments/assets/c30f02b1-2695-4e5f-9724-e01986ba799d" />

## Tools

### `accelerometer`

- Purpose: read Apple SPU accelerometer and emit mono signal.
- Args: `--rate <hz>` (<= 800), `--axis x|y|z|mag`, `--raw`.
- Notes: requires `sudo`.

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

- Purpose: emit BPM/confidence JSON lines from incoming signal (typically bandpassed).
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
- Args: `--send-hz`, `--fade-ms`, `--gain`, `--attack-ms`, `--release-ms`, `--baseline-ms`, `--decay-per-s`, `--debug`, `--as-root`.
- Alias: `keyboad-brightness` (compat typo alias).

###  `screen-brightness`

- Purpose: beat-follow display brightness control.
- Args: `--send-hz`, `--min-level`, `--max-level`, `--gain`, `--attack-ms`, `--release-ms`, `--baseline-ms`, `--decay-per-s`, `--debug`, `--no-restore`.

### `fan-speed`

- Purpose: signal-follow fan RPM control (both fans in sync by default; beat-alternating optional).
- Args: `--send-hz`, `--min-rpm`, `--max-rpm`, `--min-frac`, `--max-frac`, `--pulse-depth`, `--couple`, `--alternate`, `--input-map`, `--beat-threshold`, `--beat-hold-ms`, `--gain`, `--attack-ms`, `--release-ms`, `--baseline-ms`, `--decay-per-s`, `--debug`, `--no-restore`.

---

## Example Usage

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

Auto-follow metronome from mic input, emits a metronome tone in sync with the beat of whatever audio is playing:

```bash
microphone | metronome | speaker
```

Metronome driving keyboard pulses:

```bash
metronome 120 | keyboard-brightness
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

---

## Notes

- `accelerometer` requires root (AppleSPU HID access).
- `microphone`/`speaker` depend on `sounddevice` + PortAudio runtime.
- Keyboard/display brightness tools need supported hardware/permissions.
- `fan-speed` uses AppleSMC private IOKit APIs on Apple Silicon; writing fan targets typically requires `sudo`.
- `frequency-shift` is intentionally lightweight and artifact-prone at extreme factors.

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
