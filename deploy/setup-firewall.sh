#!/bin/bash
# ============================================================
# deploy/setup-firewall.sh
# Lightweight UFW firewall hardening for Oracle Cloud VPS
#
# Opens ONLY:
#   22   — SSH access
#   80   — HTTP (for Let's Encrypt / Nginx reverse proxy)
#   443  — HTTPS (production dashboard)
#   8000 — FastAPI direct access (optional, remove for proxy-only)
#
# Usage (run as root):
#   chmod +x deploy/setup-firewall.sh
#   sudo ./deploy/setup-firewall.sh
# ============================================================
set -euo pipefail

echo "╔══════════════════════════════════════════════╗"
echo "║  NUR BOT — Firewall Hardening (UFW)          ║"
echo "╚══════════════════════════════════════════════╝"

# ── 1. Install UFW if missing ─────────────────────────────────
if ! command -v ufw &>/dev/null; then
    echo "[SETUP] Installing UFW..."
    apt-get update -qq && apt-get install -y -qq ufw
fi

# ── 2. Reset to clean state ──────────────────────────────────
echo "[FIREWALL] Resetting UFW rules..."
ufw --force reset

# ── 3. Default policies: deny everything inbound ─────────────
echo "[FIREWALL] Setting default policies..."
ufw default deny incoming
ufw default allow outgoing

# ── 4. Allow essential ports ──────────────────────────────────
echo "[FIREWALL] Opening ports..."

# SSH — CRITICAL: always allow before enabling UFW
echo "  → Port 22/tcp  (SSH)"
ufw allow 22/tcp comment "SSH access"

# HTTP — needed for Let's Encrypt certificate renewal
echo "  → Port 80/tcp  (HTTP)"
ufw allow 80/tcp comment "HTTP / Let's Encrypt"

# HTTPS — production dashboard via Nginx reverse proxy
echo "  → Port 443/tcp (HTTPS)"
ufw allow 443/tcp comment "HTTPS / Dashboard"

# FastAPI direct — remove this rule if using Nginx reverse proxy only
echo "  → Port 8000/tcp (FastAPI direct)"
ufw allow 8000/tcp comment "FastAPI Dashboard (direct)"

# ── 5. Rate-limit SSH to prevent brute force ─────────────────
echo "[FIREWALL] Enabling SSH rate limiting..."
ufw limit 22/tcp comment "SSH rate limit (6 attempts/30s)"

# ── 6. Enable UFW ────────────────────────────────────────────
echo "[FIREWALL] Enabling firewall..."
ufw --force enable

# ── 7. Show final status ─────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Firewall Active!                             ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
ufw status verbose
echo ""
echo "  To check status anytime:  sudo ufw status"
echo "  To disable temporarily:   sudo ufw disable"
echo ""
echo "  ⚠  IMPORTANT for Oracle Cloud:"
echo "  Also configure the VCN Security List in the Oracle Cloud Console"
echo "  to allow ingress on ports 22, 80, 443, and 8000."
echo "  UFW alone is NOT sufficient — Oracle's iptables rules also apply."
echo ""
