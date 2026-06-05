#!/bin/bash
# ============================================================
# deploy/setup-systemd.sh
# Creates a systemd service so Docker Compose starts on boot
# and restarts automatically on crash.
#
# Usage (run as root on your Oracle Cloud VPS):
#   chmod +x deploy/setup-systemd.sh
#   sudo ./deploy/setup-systemd.sh
# ============================================================
set -euo pipefail

APP_DIR="/opt/nur-trading-bot"
SERVICE_NAME="nur-bot"
COMPOSE_CMD="docker compose"

echo "╔══════════════════════════════════════════════╗"
echo "║  NUR BOT — systemd Service Installer         ║"
echo "╚══════════════════════════════════════════════╝"

# ── 1. Verify Docker is installed ─────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "[ERROR] Docker is not installed. Install it first:"
    echo "  curl -fsSL https://get.docker.com | sh"
    echo "  sudo usermod -aG docker \$USER"
    exit 1
fi

# ── 2. Copy project to /opt if not already there ──────────────
if [ ! -d "$APP_DIR" ]; then
    echo "[SETUP] Copying project to $APP_DIR..."
    mkdir -p "$APP_DIR"
    echo "  Copy your project files to $APP_DIR and re-run this script."
    echo "  Example: scp -r ./Nur-main/* root@YOUR_VPS_IP:$APP_DIR/"
    exit 1
fi

# ── 3. Create the systemd unit file ──────────────────────────
echo "[SETUP] Creating systemd service: $SERVICE_NAME.service"

cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=Nur Trading Bot (Docker Compose)
Documentation=https://github.com/your-repo/Nur-main
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${APP_DIR}

# Load production environment
EnvironmentFile=-${APP_DIR}/.env

# Start containers
ExecStart=${COMPOSE_CMD} up -d --remove-orphans
# Stop containers gracefully (30s timeout)
ExecStop=${COMPOSE_CMD} down --timeout 30
# Reload: rebuild and restart
ExecReload=${COMPOSE_CMD} up -d --build --remove-orphans

# Restart policy
Restart=on-failure
RestartSec=30s

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
EOF

# ── 4. Enable and start the service ──────────────────────────
echo "[SETUP] Reloading systemd daemon..."
systemctl daemon-reload

echo "[SETUP] Enabling $SERVICE_NAME to start on boot..."
systemctl enable ${SERVICE_NAME}.service

echo "[SETUP] Starting $SERVICE_NAME now..."
systemctl start ${SERVICE_NAME}.service

# ── 5. Show status ───────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Installation Complete!                       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Service:  $SERVICE_NAME"
echo "  Status:   systemctl status $SERVICE_NAME"
echo "  Logs:     journalctl -u $SERVICE_NAME -f"
echo "  Restart:  systemctl restart $SERVICE_NAME"
echo "  Rebuild:  systemctl reload $SERVICE_NAME"
echo "  Stop:     systemctl stop $SERVICE_NAME"
echo ""
echo "  Docker logs:"
echo "    docker compose -f $APP_DIR/docker-compose.yml logs -f bot"
echo "    docker compose -f $APP_DIR/docker-compose.yml logs -f api"
echo ""

systemctl status ${SERVICE_NAME}.service --no-pager
