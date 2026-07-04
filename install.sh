#!/bin/bash
# VPLink 3.0 — one-liner installer
# Usage: bash -c "$(curl -fsSL https://raw.githubusercontent.com/adittaya/VPLINK-3.0/proxy-rotation/install.sh)"
# Or:   curl -fsSL https://raw.githubusercontent.com/adittaya/VPLINK-3.0/proxy-rotation/install.sh | bash

REPO="https://github.com/adittaya/VPLINK-3.0"
BRANCH="proxy-rotation"
DIR="$HOME/vplink3.0"
CONFIG_DIR="$HOME/.vplink"
CONFIG_FILE="$CONFIG_DIR/config.json"

# ── Termux detection ──────────────────────────────────
is_termux() { [ -n "$PREFIX" ] && [ -d /data/data/com.termux ] 2>/dev/null; }

is_termux && TERMUX=1 || TERMUX=0

SUDO=""
PKG_INSTALL=""
if is_termux; then
  PKG_INSTALL="pkg install -y"
elif command -v sudo &>/dev/null; then
  SUDO="sudo"
fi

has_tty() { [ -t 0 ]; }

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     VPLink 3.0 — Automated Installer        ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ─── Step 0: Credential setup ─────────────────────────
echo "[0/7] Supabase credentials..."

mkdir -p "$CONFIG_DIR"

# Load existing config (shell-native, no Python needed at step 0)
SAVED_URL=""; SAVED_KEY=""
if [ -f "$CONFIG_FILE" ]; then
  SAVED_URL=$(grep -o '"supabase_url"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG_FILE" | sed 's/"supabase_url"[[:space:]]*:[[:space:]]*"//;s/"$//')
  SAVED_KEY=$(grep -o '"supabase_service_key"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG_FILE" | sed 's/"supabase_service_key"[[:space:]]*:[[:space:]]*"//;s/"$//')
fi

SUPABASE_URL="${SUPABASE_URL:-$SAVED_URL}"
SUPABASE_SERVICE_KEY="${SUPABASE_SERVICE_KEY:-$SAVED_KEY}"

if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_SERVICE_KEY" ]; then
  echo "  Using saved/exported credentials"
else
  if has_tty; then
    # Interactive prompt
    echo "  Enter your Supabase project credentials."
    echo "  (Get these from https://supabase.com → Project Settings → API)"
    echo ""
    read -p "  SUPABASE_URL [${SAVED_URL:-https://project.supabase.co}]: " INPUT_URL
    SUPABASE_URL="${INPUT_URL:-${SAVED_URL:-https://project.supabase.co}}"
    read -p "  SUPABASE_SERVICE_KEY [${SAVED_KEY:+(saved)}]: " INPUT_KEY
    if [ -n "$INPUT_KEY" ]; then
      SUPABASE_SERVICE_KEY="$INPUT_KEY"
    elif [ -z "$SAVED_KEY" ]; then
      echo "  ERROR: SUPABASE_SERVICE_KEY is required."
      exit 1
    fi
  else
    echo "  ERROR: No credentials found."
    echo "  Set SUPABASE_URL and SUPABASE_SERVICE_KEY env vars,"
    echo "  or run interactively in a terminal."
    exit 1
  fi
fi

# Validate basic URL format
if ! echo "$SUPABASE_URL" | grep -qE '^https?://.+'; then
  echo "  ERROR: SUPABASE_URL must be a valid URL"
  exit 1
fi

# Save permanently
cat > "$CONFIG_FILE" << EOF
{
  "supabase_url": "$SUPABASE_URL",
  "supabase_service_key": "$SUPABASE_SERVICE_KEY"
}
EOF
chmod 600 "$CONFIG_FILE"
echo "  Credentials saved to $CONFIG_FILE"
echo ""

# ─── Step 1: System dependencies ─────────────────────
detect_pkg_manager() {
  if is_termux; then echo "pkg"
  elif command -v apt &>/dev/null; then echo "apt"
  elif command -v yum &>/dev/null; then echo "yum"
  elif command -v dnf &>/dev/null; then echo "dnf"
  elif command -v pacman &>/dev/null; then echo "pacman"
  elif command -v zypper &>/dev/null; then echo "zypper"
  elif command -v apk &>/dev/null; then echo "apk"
  else echo "unknown"; fi
}

install_system_deps() {
  PKG_MANAGER=$(detect_pkg_manager)
  echo "  Package manager: $PKG_MANAGER"
  echo "  Platform: $([ "$TERMUX" = 1 ] && echo 'Termux (Android)' || echo 'Standard Linux')"

  if [ "$TERMUX" = 1 ]; then
    pkg update -y
    pkg install -y x11-repo
    pkg install -y curl git chromium nodejs python
  else
    case "$PKG_MANAGER" in
      apt)
        if grep -qi "ubuntu 24" /etc/os-release 2>/dev/null || grep -qi "ubuntu 25" /etc/os-release 2>/dev/null || grep -qi "debian 13" /etc/os-release 2>/dev/null; then
          LIBPOSTFIX="t64"
        else
          LIBPOSTFIX=""
        fi
        PLAYWRIGHT_DEPS="libnss3 libnspr4 libatk1.0-0${LIBPOSTFIX} libatk-bridge2.0-0${LIBPOSTFIX} libcups2${LIBPOSTFIX} libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2"
        ASOUND="libasound2${LIBPOSTFIX}"
        $SUDO apt update -qq
        $SUDO apt install -y -qq curl git xvfb x11vnc $PLAYWRIGHT_DEPS $ASOUND python3 python3-pip
        ;;
      yum|dnf)
        $SUDO $PKG_MANAGER install -y curl git xorg-x11-server-Xvfb x11vnc nss nspr atk at-spi2-atk cups-libs libdrm dbus-libs libxkbcommon libXcomposite libXdamage libXfixes libXrandr libgbm pango cairo alsa-lib python3 python3-pip
        ;;
      pacman)
        $SUDO pacman -Sy --noconfirm curl git xorg-server-xvfb x11vnc nss nspr atk at-spi2-atk cups libdrm dbus libxkbcommon libxcomposite libxdamage libxfixes libxrandr libgbm pango cairo alsa-lib python python-pip
        ;;
      zypper)
        $SUDO zypper install -y curl git xvfb x11vnc nss nspr atk at-spi2-atk cups-libs libdrm dbus-1 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 pango cairo alsa-lib python3 python3-pip
        ;;
      apk)
        $SUDO apk add curl git xvfb x11vnc nss nspr atk at-spi2-atk cups-libs libdrm dbus libxkbcommon libxcomposite libxdamage libxfixes libxrandr libgbm pango cairo alsa-lib python3 py3-pip
        ;;
      *)
        echo "  WARNING: Unknown package manager. Install curl, git, node, python3 manually."
        ;;
    esac
  fi
}

echo "[1/7] Installing system dependencies..."
install_system_deps
echo ""

# ─── Step 2: Node.js ──────────────────────────────────
echo "[2/7] Checking Node.js..."
if command -v node &>/dev/null && [ "$(node -v | cut -d. -f1 | tr -d v)" -ge 18 ]; then
  echo "  Node.js $(node -v) already installed"
elif [ "$TERMUX" = 1 ]; then
  echo "  Installing Node.js via pkg..."
  pkg install -y nodejs
  echo "  Node.js $(node -v) installed"
elif command -v snap &>/dev/null && $SUDO snap install node --classic 2>/dev/null; then
  echo "  Node.js $(node -v) installed via snap"
else
  echo "  Installing Node.js via nodesource..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | $SUDO -E bash - &>/dev/null
  $SUDO apt install -y -qq nodejs &>/dev/null
  echo "  Node.js $(node -v) installed"
fi
echo ""

# ─── Step 3: Clone repo ───────────────────────────────
echo "[3/7] Setting up VPLink 3.0..."
if [ -d "$DIR" ]; then
  echo "  Updating existing installation..."
  cd "$DIR" && git pull
else
  echo "  Cloning repo..."
  git clone -b "$BRANCH" "$REPO" "$DIR"
fi
cd "$DIR"
echo ""

# ─── Step 4: Python dependencies ──────────────────────
echo "[4/7] Installing Python dependencies..."
if command -v pip3 &>/dev/null; then
  pip3 install httpx -q 2>/dev/null || true
fi
echo ""

# ─── Step 5: npm + Playwright ─────────────────────────
echo "[5/7] Installing Playwright + browsers..."
if [ "$TERMUX" = 1 ]; then
  npm install playwright-core 2>&1 | tail -2
  echo "  Termux: using system Chromium"
else
  npm install 2>&1 | tail -2
  npx playwright install chromium 2>&1 | tail -1
fi
echo ""

# ─── Step 6: Install command ─────────────────────────
echo "[6/7] Installing vplink3.0 command..."
chmod +x "$DIR/proxy_manager.py"
chmod +x "$DIR/proxy_cleaner.py"
chmod +x "$DIR/vplink3.0.sh"
if [ "$TERMUX" = 1 ]; then
  cp "$DIR/vplink3.0.sh" "$PREFIX/bin/vplink3.0"
  chmod +x "$PREFIX/bin/vplink3.0"
else
  $SUDO ln -sf "$DIR/vplink3.0.sh" /usr/local/bin/vplink3.0
fi
echo ""

# ─── Step 7: Install command ─────────────────────────
echo "[7/7] Config persisted at $CONFIG_FILE"
echo ""

# ─── Done ────────────────────────────────────────────
echo "╔══════════════════════════════════════════════╗"
echo "║  Installation complete!                      ║"
echo "║                                              ║"
echo "║  Run: vplink3.0                              ║"
echo "║  Config: $CONFIG_FILE"
echo "╚══════════════════════════════════════════════╝"
