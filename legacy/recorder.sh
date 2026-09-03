#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
TIMESTAMP=$(date +%Y-%m-%dT%H-%M-%S)
RECORDING_DIR="$SCRIPT_DIR/recording_$TIMESTAMP"
SCREENSHOTS_DIR="$RECORDING_DIR/screenshots"
SNAPSHOTS_DIR="$RECORDING_DIR/snapshots"
mkdir -p "$SCREENSHOTS_DIR" "$SNAPSHOTS_DIR"

VNC_PORT="${1:-5900}"
DISPLAY_NUM="${2:-99}"
KEY="${3:-${FLOW_KEY:-example}}"

cleanup() {
  echo ""
  echo "[recorder] Cleaning up..."
  kill ${RECORDER_PID:-} 2>/dev/null || true
  kill ${NODE_PID:-} 2>/dev/null || true
  kill ${XVFB_PID:-} 2>/dev/null || true
  kill ${VNC_PID:-} 2>/dev/null || true
  rm -f "/tmp/.X${DISPLAY_NUM}-lock" "/tmp/.X11-unix/X${DISPLAY_NUM}"
  echo "[recorder] Done. Recording saved to: $RECORDING_DIR"
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "[recorder] Starting Xvfb on :${DISPLAY_NUM}..."
Xvfb ":${DISPLAY_NUM}" -screen 0 1920x1080x24 &
XVFB_PID=$!
sleep 1

echo "[recorder] Starting x11vnc on port ${VNC_PORT}..."
x11vnc -display ":${DISPLAY_NUM}" -rfbport "$VNC_PORT" -forever -quiet &
VNC_PID=$!
sleep 1

export DISPLAY=":${DISPLAY_NUM}"

echo "[recorder] Starting recorder script..."
node "$SCRIPT_DIR/recorder.js" "$RECORDING_DIR" "$KEY" &
RECORDER_PID=$!

echo ""
echo "═══════════════════════════════════════════════════"
echo "  RECORDER ACTIVE"
echo "  VNC: connect to localhost:${VNC_PORT}"
echo "  Recording: $RECORDING_DIR"
echo "  Press Ctrl+C to stop and save"
echo "═══════════════════════════════════════════════════"
echo ""

wait $RECORDER_PID
cleanup
