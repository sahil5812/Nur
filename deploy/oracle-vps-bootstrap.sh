#!/bin/bash
# ============================================================
# deploy/oracle-vps-bootstrap.sh
# One-shot bootstrap for a fresh Oracle Cloud "Always Free" VPS
# (Ubuntu 22.04 / Oracle Linux 8+)
#
# This script installs Docker, Docker Compose, UFW,
# copies the project, and sets up systemd auto-start.
#
# Usage:
#   1. SSH into your VPS:  ssh ubuntu@YOUR_VPS_IP
#   2. Upload project:     scp -r Nur-main/ ubuntu@IP:~/
#   3. Run this script:    sudo bash ~/Nur-main/deploy/oracle-vps-bootstrap.sh
# ============================================================
set -euo pipefail

APP_DIR="/opt/nur-trading-bot"

echo "╔══════════════════════════════════════════════╗"
echo "║  NUR BOT — Oracle Cloud VPS Bootstrap        ║"
echo "║  Always-Free Tier Deployment                  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── 1. System Update ─────────────────────────────────────────
echo "[1/6] Updating system packages..."
apt-get update -qq && apt-get upgrade -y -qq

# ── 2. Install Docker ────────────────────────────────────────
echo "[2/6] Installing Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    # Add current user to docker group (takes effect on next login)
    usermod -aG docker "${SUDO_USER:-ubuntu}" 2>/dev/null || true
    echo "  Docker installed successfully"
else
    echo "  Docker already installed"
fi

# ── 3. Copy project to /opt ──────────────────────────────────
echo "[3/6] Setting up application directory..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -d "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/docker-compose.yml" ]; then
    mkdir -p "$APP_DIR"
    rsync -a --exclude='.venv' --exclude='node_modules' --exclude='__pycache__' \
          --exclude='.git' --exclude='venv_backup' \
          "$SCRIPT_DIR/" "$APP_DIR/"
    echo "  Project copied to $APP_DIR"
else
    echo "  [WARN] Could not locate project source. Copy manually:"
    echo "    rsync -a ~/Nur-main/ $APP_DIR/"
fi

# ── 4. Production .env ───────────────────────────────────────
echo "[4/6] Setting up production environment..."
if [ ! -f "$APP_DIR/.env" ]; then
    if [ -f "$APP_DIR/.env.production" ]; then
        cp "$APP_DIR/.env.production" "$APP_DIR/.env"
        echo "  .env created from .env.production template"
        echo "  ⚠  EDIT IT NOW:  nano $APP_DIR/.env"
    else
        echo "  [WARN] No .env.production template found"
    fi
else
    echo "  .env already exists — skipping"
fi

# ── 5. Firewall ──────────────────────────────────────────────
echo "[5/6] Configuring firewall..."
if [ -f "$APP_DIR/deploy/setup-firewall.sh" ]; then
    bash "$APP_DIR/deploy/setup-firewall.sh"
else
    echo "  [WARN] Firewall script not found — skipping"
fi

# ── 6. Systemd Service ──────────────────────────────────────
echo "[6/6] Installing systemd service..."
if [ -f "$APP_DIR/deploy/setup-systemd.sh" ]; then
    bash "$APP_DIR/deploy/setup-systemd.sh"
else
    echo "  [WARN] Systemd script not found — skipping"
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Bootstrap Complete!                          ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  ┌─────────────────────────────────────────┐"
echo "  │  NEXT STEPS:                            │"
echo "  │                                         │"
echo "  │  1. Edit credentials:                   │"
echo "  │     nano $APP_DIR/.env                  │"
echo "  │                                         │"
echo "  │  2. Start the bot:                      │"
echo "  │     systemctl start nur-bot             │"
echo "  │                                         │"
echo "  │  3. Check status:                       │"
echo "  │     docker compose -f \\                 │"
echo "  │       $APP_DIR/docker-compose.yml \\     │"
echo "  │       logs -f                           │"
echo "  │                                         │"
echo "  │  4. Dashboard:                          │"
echo "  │     http://YOUR_VPS_IP:8000             │"
echo "  │                                         │"
echo "  │  5. Oracle Cloud Console:               │"
echo "  │     Open ports 22, 80, 443, 8000        │"
echo "  │     in VCN > Security Lists > Ingress   │"
echo "  └─────────────────────────────────────────┘"
echo ""
