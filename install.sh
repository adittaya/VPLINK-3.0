#!/bin/bash
set -e

REPO="https://github.com/adittaya/VPLINK-3.0"
DIR="$HOME/vplink3.0"

# ── Termux detection ──────────────────────────────────
is_termux() {
  [ -n "$PREFIX" ] && [ -d /data/data/com.termux ] 2>/dev/null
}

SUDO=""
PKG_INSTALL=""
TERMUX=0

if is_termux; then
  TERMUX=1
  PKG_INSTALL="pkg install -y"
  SUDO=""
elif command -v sudo &>/dev/null; then
  SUDO="sudo"
fi

echo "╔══════════════════════════════════════════════╗"
echo "║        VPLink 3.0 — Automated Installer      ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

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
    # Termux: install Chromium via x11-repo, no Xvfb/VNC
    pkg update -y
    pkg install -y x11-repo
    pkg install -y curl git chromium nodejs
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
        $SUDO apt install -y -qq curl git xvfb x11vnc $PLAYWRIGHT_DEPS $ASOUND
        ;;
      yum|dnf)
        $SUDO $PKG_MANAGER install -y curl git xorg-x11-server-Xvfb x11vnc nss nspr atk at-spi2-atk cups-libs libdrm dbus-libs libxkbcommon libXcomposite libXdamage libXfixes libXrandr libgbm pango cairo alsa-lib
        ;;
      pacman)
        $SUDO pacman -Sy --noconfirm curl git xorg-server-xvfb x11vnc nss nspr atk at-spi2-atk cups libdrm dbus libxkbcommon libxcomposite libxdamage libxfixes libxrandr libgbm pango cairo alsa-lib
        ;;
      zypper)
        $SUDO zypper install -y curl git xvfb x11vnc nss nspr atk at-spi2-atk cups-libs libdrm dbus-1 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 pango cairo alsa-lib
        ;;
      apk)
        $SUDO apk add curl git xvfb x11vnc nss nspr atk at-spi2-atk cups-libs libdrm dbus libxkbcommon libxcomposite libxdamage libxfixes libxrandr libgbm pango cairo alsa-lib
        ;;
      *)
        echo "  WARNING: Unknown package manager. Install manually."
        ;;
    esac
  fi
}

# ── 1. System dependencies ──────────────────────────
echo "[1/7] Installing system dependencies..."
install_system_deps
echo ""

# ── 2. Node.js ──────────────────────────────────────
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

# ── 3. Clone repo ───────────────────────────────────
echo "[3/7] Setting up VPLink 3.0..."
if [ -d "$DIR" ]; then
  echo "  Updating existing installation..."
  cd "$DIR" && git pull
else
  echo "  Cloning repo..."
  git clone "$REPO" "$DIR"
fi
cd "$DIR"
echo ""

# ── 4. Clone proxy-hunter repo ──────────────────────
echo "[4/7] Installing proxy hunter..."
HUNTER_DIR="$HOME/vplink-proxy-hunter"
if [ -d "$HUNTER_DIR" ]; then
  echo "  Proxy hunter already exists at $HUNTER_DIR"
else
  echo "  Cloning vplink-proxy-hunter..."
  git clone --depth 1 https://github.com/adittaya/vplink-proxy-hunter.git "$HUNTER_DIR"
fi
echo ""

# ── 5. Install Python dependencies ──────────────────
echo "[5/7] Installing Python dependencies..."
if command -v pip3 &>/dev/null; then
  pip3 install supabase httpx -q 2>/dev/null || true
fi
echo ""

# ── 6. Install npm dependencies & Playwright ────────
echo "[6/7] Installing Playwright + browsers..."
if [ "$TERMUX" = 1 ]; then
  # Termux: use playwright-core + system Chromium
  npm install playwright-core 2>&1 | tail -2
  echo "  Termux: using system Chromium at $(which chromium-browser || which chromium)"
else
  npm install 2>&1 | tail -2
  npx playwright install chromium 2>&1 | tail -1
fi
echo ""

# ── 7. Install command ─────────────────────────────
echo "[7/7] Installing vplink3.0 command..."
chmod +x "$DIR/proxy_manager.py"
if [ "$TERMUX" = 1 ]; then
  cp "$DIR/vplink3.0.sh" "$PREFIX/bin/vplink3.0"
  chmod +x "$PREFIX/bin/vplink3.0"
else
  $SUDO cp "$DIR/vplink3.0.sh" /usr/local/bin/vplink3.0
  $SUDO chmod +x /usr/local/bin/vplink3.0
fi
echo ""

# ── Done ────────────────────────────────────────────
echo "╔══════════════════════════════════════════════╗"
echo "║  Installation complete!                      ║"
echo "║                                              ║"
echo "║  Run: vplink3.0                              ║"
echo "╚══════════════════════════════════════════════╝"
