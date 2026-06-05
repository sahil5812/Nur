# ============================================================
# Nur Trading Bot — Production Dockerfile
# Multi-stage build: Wine + Xvfb for MT5 headless on Linux
# ============================================================

FROM python:3.11-slim-bookworm AS base

LABEL maintainer="Nur Trading Bot"
LABEL description="XAUUSD trading bot with MT5, RL agent, and FastAPI dashboard"

# ── System Dependencies ──────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DISPLAY=:99

RUN apt-get update && apt-get install -y --no-install-recommends \
    # Wine for running MT5 (Windows binary) on Linux
    dpkg-dev \
    wget \
    gnupg2 \
    software-properties-common \
    # Virtual framebuffer for headless MT5 GUI
    xvfb \
    x11-utils \
    # Build dependencies
    build-essential \
    libpq-dev \
    curl \
    cabextract \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# ── Install Wine (32+64 bit) for MetaTrader5 ─────────────────
RUN dpkg --add-architecture i386 \
    && mkdir -pm755 /etc/apt/keyrings \
    && wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key \
    && wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/debian/dists/bookworm/winehq-bookworm.sources \
    && apt-get update \
    && apt-get install -y --install-recommends winehq-stable \
    && rm -rf /var/lib/apt/lists/*

# ── Install winetricks for font/DLL fixups ────────────────────
RUN wget -O /usr/local/bin/winetricks https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks \
    && chmod +x /usr/local/bin/winetricks

# ── Application Setup ────────────────────────────────────────
WORKDIR /app

# Copy requirements first (Docker layer caching)
COPY requirements.txt .
COPY requirements.docker.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements.docker.txt

# Copy entire project
COPY . .

# ── Persistent Data Volumes ──────────────────────────────────
RUN mkdir -p /app/logs /app/database /app/data

VOLUME ["/app/database", "/app/logs", "/app/data", "/app/rl/models"]

# ── Ports ─────────────────────────────────────────────────────
# FastAPI dashboard
EXPOSE 8000

# ── Entrypoint Script ─────────────────────────────────────────
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
