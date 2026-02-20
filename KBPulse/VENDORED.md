# KBPulse (Vendored)

This folder vendors the upstream KBPulse source into this repository so `motion_live.py` can drive keyboard backlight intensity directly.

## Upstream
- Source project: https://github.com/EthanRDoesMC/KBPulse
- License: `KBPulse/LICENSE`

## Local integration notes
- `KBPulse/KBPulse/main.m` adds a `--stdin-intensity` mode for realtime brightness streaming.
- A prebuilt Apple Silicon binary is committed at `KBPulse/bin/KBPulse`.
- Rebuild command: `./scripts/rebuild_kbpulse_binary.sh`
