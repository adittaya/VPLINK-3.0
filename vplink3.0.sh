#!/bin/bash
# VPLink 3.0 — ad funnel automation with IP rotation + Android profiles
# Usage: vplink3.0 [--key KEY] [--views N] [--no-proxy] [--no-yt] [--vnc] [--clean]

# ─── Path resolution ──────────────────────────────
# Resolve symlink to real path so SCRIPT_DIR works when installed via symlink
SELF="$(readlink -f "$0" 2>/dev/null || realpath "$0" 2>/dev/null || echo "$0")"
SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd)"
# Fallback: if files not in resolved dir, check install dir
[ ! -f "$SCRIPT_DIR/generated_automation.js" ] && [ -f "$HOME/vplink3.0/generated_automation.js" ] && SCRIPT_DIR="$HOME/vplink3.0"

AUTOMATION="$SCRIPT_DIR/generated_automation.js"
PROXY_MGR="$SCRIPT_DIR/proxy_manager.py"
PROXY_CLN="$SCRIPT_DIR/proxy_cleaner.py"
PID_FILE="/tmp/vplink_pids_$$"
VIEW_TIMEOUT=480
SELF_PPID=$$

# ─── Android Profiles ──────────────────────────────────────────────
# 20 devices: name | userAgent | viewport_w | viewport_h | dpr | isMobile:1 | hasTouch:1
PROFILES=(
  "S24U|Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36|412|915|2.625|1|1"
  "S23|Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.179 Mobile Safari/537.36|360|780|3.0|1|1"
  "S22|Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.118 Mobile Safari/537.36|360|780|3.0|1|1"
  "Pix8P|Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36|412|915|2.625|1|1"
  "Pix7|Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.179 Mobile Safari/537.36|412|846|2.625|1|1"
  "Pix6|Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.118 Mobile Safari/537.36|393|830|2.75|1|1"
  "OP12|Mozilla/5.0 (Linux; Android 14; CPH2573) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36|412|915|2.625|1|1"
  "OP11|Mozilla/5.0 (Linux; Android 14; CPH2449) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.179 Mobile Safari/537.36|393|852|2.75|1|1"
  "OP10P|Mozilla/5.0 (Linux; Android 13; NE2210) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.118 Mobile Safari/537.36|393|852|2.75|1|1"
  "X14P|Mozilla/5.0 (Linux; Android 14; 23127PN0CG) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36|393|852|2.75|1|1"
  "X13|Mozilla/5.0 (Linux; Android 14; 2211133G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.179 Mobile Safari/537.36|393|852|2.75|1|1"
  "X12|Mozilla/5.0 (Linux; Android 13; 2203123C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.118 Mobile Safari/537.36|360|780|3.0|1|1"
  "F7U|Mozilla/5.0 (Linux; Android 14; PHZ110) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36|412|915|2.625|1|1"
  "F5P|Mozilla/5.0 (Linux; Android 13; PFEM10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.118 Mobile Safari/537.36|393|852|2.75|1|1"
  "V100P|Mozilla/5.0 (Linux; Android 14; V2324A) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.179 Mobile Safari/537.36|393|852|2.75|1|1"
  "V90|Mozilla/5.0 (Linux; Android 13; V2217A) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.118 Mobile Safari/537.36|393|852|2.75|1|1"
  "NP2|Mozilla/5.0 (Linux; Android 14; A065) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.179 Mobile Safari/537.36|393|830|2.75|1|1"
  "RG5|Mozilla/5.0 (Linux; Android 14; RMX3823) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36|393|852|2.75|1|1"
  "HM6P|Mozilla/5.0 (Linux; Android 14; BVL-AN16) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36|393|852|2.75|1|1"
  "AZ11|Mozilla/5.0 (Linux; Android 14; ASUS_AI2501C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.179 Mobile Safari/537.36|412|915|2.625|1|1"
)

# ─── YouTube video pool ────────────────────────────────────────────
YT_VIDS=(
  "dQw4w9WgXcQ" "jx5h7HvdcK4" "kXYiU_JCYtU" "RgKAFK5djSk"
  "JGwWNGJdvx8" "HhesaQXLuRY" "WA4iX5D9G64" "9bZkp7q19f0"
  "hT_nvWreIhg" "OPf0YbXqDm0" "60ItHLz5WEA" "fJ9rUzIMcZQ"
)

# ─── Parse flags ──────────────────────────────────
ARG_KEY=""; ARG_VIEWS=""; ARG_NOPROXY=0; ARG_VNC=0; ARG_CLEAN=0; ARG_NOYT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --key) ARG_KEY="$2"; shift 2 ;;
    --views) ARG_VIEWS="$2"; shift 2 ;;
    --no-proxy) ARG_NOPROXY=1; shift ;;
    --no-yt) ARG_NOYT=1; shift ;;
    --vnc) ARG_VNC=1; shift ;;
    --clean) ARG_CLEAN=1; shift ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

# ─── Detect Termux ────────────────────────────────
is_termux() { [ -n "$PREFIX" ] && [ -d /data/data/com.termux ] 2>/dev/null; }
is_termux && TERMUX=1 || TERMUX=0

# ─── PID tracking: only kill what we start ────────
# We track Xvfb and x11vnc globally.
# Chrome processes are tracked PER VIEW via user data dir path.
track_pid() { echo "$1" >> "$PID_FILE"; }

kill_own() {
  [ -f "$PID_FILE" ] || return 0
  while read -r pid; do
    # Never kill our own shell or PIDs from other sessions
    [ "$pid" = "$SELF_PPID" ] && continue
    kill "$pid" 2>/dev/null || true
  done < "$PID_FILE"
  rm -f "$PID_FILE"
  rm -f /tmp/.X99-lock /tmp/.X11-unix/X99 2>/dev/null
}

kill_chrome_by_data_dir() {
  local data_dir="$1"
  [ -z "$data_dir" ] && return 0
  local chrome_pids
  chrome_pids=$(ps aux 2>/dev/null | grep -E "[C]hromium|[C]hrome" | grep -F "$data_dir" | awk '{print $2}')
  [ -z "$chrome_pids" ] && return 0
  for pid in $chrome_pids; do
    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 1
    done
    kill -9 "$pid" 2>/dev/null || true
  done
}

cleanup() {
  kill_own
  # Clean Chrome user data dirs belonging to this session
  for dir in /tmp/vplink_chrome_${$}_*; do
    [ -d "$dir" ] || continue
    kill_chrome_by_data_dir "$dir"
    rm -rf "$dir" 2>/dev/null
  done
  rm -f /tmp/vplink_our_xvfb 2>/dev/null
  local orphan
  orphan=$(pgrep -P "$SELF_PPID" 2>/dev/null | grep -v "^$SELF_PPID$" || true)
  [ -n "$orphan" ] && kill $orphan 2>/dev/null || true
}
trap 'echo ""; echo "  Interrupted."; cleanup; exit 130' SIGINT
trap 'cleanup' EXIT

# ─── Banner ───────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║        VPLink 3.0 — Funnel Automation        ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

# ─── Key ──────────────────────────────────────────
if [ -n "$ARG_KEY" ]; then KEY="$ARG_KEY"
else read -p "  Enter vplink URL or key: " INPUT
  KEY=$(echo "$INPUT" | sed 's|https\?://vplink.in/||' | xargs)
fi
[ -z "$KEY" ] && { echo "  Error: no key"; exit 1; }

# ─── Views ────────────────────────────────────────
if [ -n "$ARG_VIEWS" ]; then VIEWS="$ARG_VIEWS"
else read -p "  Views (1-50, default 1): " VIEWS
fi
[[ ! "$VIEWS" =~ ^[0-9]+$ ]] || [ "$VIEWS" -lt 1 ] && VIEWS=1
[ "$VIEWS" -gt 50 ] && VIEWS=50

# ─── VNC — auto-detect existing server ────────────
VNC_DISPLAY=""
if [ "$TERMUX" = 0 ]; then
  VNC_ASK="$ARG_VNC"
  [ -n "$VPLINK_VNC" ] && VNC_ASK=1
  if [ "$VNC_ASK" != 1 ] && [ -z "$ARG_KEY" ]; then
    VNC_PORT=""
    if command -v ss &>/dev/null; then
      VNC_PORT=$(ss -tlnp 2>/dev/null | grep ':590[0-5]' | head -1 | awk '{print $4}' | rev | cut -d: -f1 | rev)
    elif command -v netstat &>/dev/null; then
      VNC_PORT=$(netstat -tlnp 2>/dev/null | grep ':590[0-5]' | head -1 | awk '{print $4}' | rev | cut -d: -f1 | rev)
    fi
    if [ -n "$VNC_PORT" ] || pgrep -x x11vnc &>/dev/null; then
      echo "  [i] VNC server detected (port ${VNC_PORT:-5900})"
      read -p "  Use existing VNC? (Y/n): " ANS
      [ "$ANS" != "n" ] && [ "$ANS" != "N" ] && VNC_ASK=1
    fi
  fi
  if [ "$VNC_ASK" = 1 ]; then
    VNC_PORT="${VNC_PORT:-5900}"
    read -p "  VNC port [${VNC_PORT}]: " VNC_PORT_IN
    [ -n "$VNC_PORT_IN" ] && VNC_PORT="$VNC_PORT_IN"
    VNC_DISPLAY=":99"
    echo "  VNC: ${VNC_DISPLAY} → port ${VNC_PORT}"
  fi
fi

# ─── YouTube referral ─────────────────────────────
YT_URL=""
if [ "$ARG_NOYT" != 1 ]; then
  if [ -n "$ARG_KEY" ]; then
    RAND=$((RANDOM % ${#YT_VIDS[@]}))
    YT_URL="https://www.youtube.com/watch?v=${YT_VIDS[$RAND]}"
  else
    echo ""
    read -p "  YouTube traffic link (Enter=random): " YT_INPUT
    if [ -n "$YT_INPUT" ]; then
      YT_URL="$YT_INPUT"
    else
      RAND=$((RANDOM % ${#YT_VIDS[@]}))
      YT_URL="https://www.youtube.com/watch?v=${YT_VIDS[$RAND]}"
    fi
  fi
  echo "  Referrer: $YT_URL"
fi

# ─── Proxy rotation ───────────────────────────────
if [ "$ARG_NOPROXY" = 1 ]; then
  ROTATE=0
else
  ROTATE=1
  if [ -z "$ARG_KEY" ]; then
    read -p "  Rotate IP per view? (Y/n): " ANS
    [ "$ANS" = "n" ] || [ "$ANS" = "N" ] && ROTATE=0
  fi
  if [ "$ROTATE" = 1 ]; then
    if [ "$ARG_CLEAN" = 1 ]; then
      echo "  → Running proxy pool cleaner..."
      python3 "$PROXY_CLN" --scan 2>&1
    elif [ -z "$ARG_KEY" ]; then
      read -p "  Clean dead proxies first? (y/N): " ANS
      [ "$ANS" = "y" ] || [ "$ANS" = "Y" ] && python3 "$PROXY_CLN" --scan 2>&1
    fi
    echo "  → Syncing proxy pool from Supabase..."
    python3 "$PROXY_MGR" --sync 2>&1
  fi
fi

# ─── Summary ──────────────────────────────────────
echo ""
echo "  Starting $VIEWS view(s) — key: $KEY"
[ "$TERMUX" = 1 ] && echo "  Mode: Termux (headless)"
[ "$ROTATE" = 1 ] && echo "  Proxy: rotation enabled" || echo "  Proxy: disabled"
[ -n "$VNC_DISPLAY" ] && echo "  VNC: ${VNC_DISPLAY} → port ${VNC_PORT}"
[ -n "$YT_URL" ] && echo "  Referrer: YouTube"
echo ""

# ─── Env setup ────────────────────────────────────
export NODE_PATH="$SCRIPT_DIR/node_modules"
export VPLINK_TERMUX="$TERMUX"
export VPLINK_DIR="$SCRIPT_DIR"
[ -n "$YT_URL" ] && export VPLINK_REFERER="$YT_URL"

# ─── Start display (Linux) ───────────────────────
if [ "$TERMUX" = 0 ]; then
  if [ -f /tmp/vplink_our_xvfb ] && kill "$(cat /tmp/vplink_our_xvfb)" 2>/dev/null; then
    rm -f /tmp/.X99-lock /tmp/.X11-unix/X99 2>/dev/null
    sleep 1
  fi
  Xvfb :99 -screen 0 1280x720x24 &>/dev/null &
  echo $! > /tmp/vplink_our_xvfb
  track_pid $!
  sleep 2
  if ! kill -0 "$(cat /tmp/vplink_our_xvfb)" 2>/dev/null; then
    Xvfb :99 -screen 0 1280x720x24 &>/dev/null &
    echo $! > /tmp/vplink_our_xvfb
    track_pid $!
    sleep 2
  fi
  export DISPLAY=:99
  if [ -n "$VNC_DISPLAY" ]; then
    if ! ss -tlnp 2>/dev/null | grep -q ":${VNC_PORT} "; then
      x11vnc -display :99 -forever -shared -rfbport "$VNC_PORT" &>/dev/null &
      track_pid $!
      sleep 1
    fi
    echo "  VNC ready on port $VNC_PORT"
  fi
fi

# ─── View loop ────────────────────────────────────
FAILS=0
for (( i=1; i<=VIEWS; i++ )); do
  echo ""
  echo "  ─── View $i of $VIEWS ───"
  echo ""

  # Pick random Android profile
  P_COUNT=${#PROFILES[@]}
  P_IDX=$((RANDOM % P_COUNT))
  IFS='|' read -r P_NAME P_UA P_VP_W P_VP_H P_DPR P_MOBILE P_TOUCH <<< "${PROFILES[$P_IDX]}"
  export VPLINK_UA="$P_UA"
  export VPLINK_VP_W="$P_VP_W"
  export VPLINK_VP_H="$P_VP_H"
  export VPLINK_DPR="$P_DPR"
  export VPLINK_MOBILE="$P_MOBILE"
  export VPLINK_TOUCH="$P_TOUCH"
  echo "  Device: $P_NAME  (${P_VP_W}x${P_VP_H}@${P_DPR}x)"

  # Unique Chrome user data dir per view — isolates cookies/cache/fingerprint
  CHROME_DATA_DIR="/tmp/vplink_chrome_${$}_${i}"
  mkdir -p "$CHROME_DATA_DIR"
  export VPLINK_USER_DATA_DIR="$CHROME_DATA_DIR"

  # Get proxy
  if [ "$ROTATE" = 1 ]; then
    PROXY_LINE=$(python3 "$PROXY_MGR" --next 2>&1)
    PROXY_URL=$(echo "$PROXY_LINE" | grep "://")
    if [ -n "$PROXY_URL" ]; then
      export VPLINK_PROXY="$PROXY_URL"
      echo "  Proxy:  ${PROXY_URL#http://}"
    else
      echo "  Proxy:  NONE (direct)"
      unset VPLINK_PROXY
    fi
  fi

  # Run automation
  cd "$SCRIPT_DIR"
  TS=$(date +%H:%M:%S)
  timeout $VIEW_TIMEOUT node "$AUTOMATION" "$KEY"
  EXIT_CODE=$?

  # ── Per-view cleanup: kill ONLY this view's Chrome ──
  kill_chrome_by_data_dir "$CHROME_DATA_DIR"
  rm -rf "$CHROME_DATA_DIR" 2>/dev/null
  unset VPLINK_USER_DATA_DIR

  # Mark proxy used
  if [ "$ROTATE" = 1 ] && [ -n "$VPLINK_PROXY" ]; then
    python3 "$PROXY_MGR" --mark-used "$VPLINK_PROXY" 2>/dev/null || true
  fi

  # Collect result
  RESULT=""
  if [ -f "$SCRIPT_DIR/destination_url.txt" ]; then
    RESULT=$(cat "$SCRIPT_DIR/destination_url.txt")
    mv "$SCRIPT_DIR/destination_url.txt" "$SCRIPT_DIR/destination_url_${i}.txt"
  fi

  if [ -n "$RESULT" ]; then
    echo "  Result: $RESULT"
  else
    echo "  Result: none"
    [ $EXIT_CODE -ne 0 ] && ((FAILS++))
  fi

  sleep 1
done

# ─── Final cleanup (only our PIDs) ────────────────
cleanup

# ─── Results ──────────────────────────────────────
echo ""
echo "  ═══════════════════════════════════════════════"
echo "  All $VIEWS view(s) completed  ($FAILS failed)"
echo "  ═══════════════════════════════════════════════"
for (( i=1; i<=VIEWS; i++ )); do
  [ -f "$SCRIPT_DIR/destination_url_${i}.txt" ] && echo "  $i. $(cat "$SCRIPT_DIR/destination_url_${i}.txt")"
done
echo ""
echo "  Results: $SCRIPT_DIR/destination_url_*.txt"
echo ""
