#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT_DIR/KBPulse/bin/KBPulse"

mkdir -p "$(dirname "$OUT")"

xcrun clang -fobjc-arc \
  -framework Foundation \
  -framework Cocoa \
  -I "$ROOT_DIR/KBPulse/KBPulse" \
  "$ROOT_DIR/KBPulse/KBPulse/main.m" \
  "$ROOT_DIR/KBPulse/KBPulse/KBPPulseManager.m" \
  "$ROOT_DIR/KBPulse/KBPulse/KBPAnimator.m" \
  "$ROOT_DIR/KBPulse/KBPulse/KBPProfile.m" \
  "$ROOT_DIR/KBPulse/KBPulse/KBPAnimation.m" \
  -o "$OUT"

chmod 755 "$OUT"

echo "Built $OUT"
