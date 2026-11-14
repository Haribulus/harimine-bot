#!/usr/bin/env bash
set -e

SERVICE_NAME="harimine-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🛑 Stopping and removing $SERVICE_NAME service..."

if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
    sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    sudo systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    echo "✅ Service stopped and disabled."
fi

if [ -f "$SERVICE_FILE" ]; then
    sudo rm -f "$SERVICE_FILE"
    sudo systemctl daemon-reload
    sudo systemctl reset-failed 2>/dev/null || true
    echo "🗑️ Removed $SERVICE_FILE."
else
    echo "ℹ️ Service file $SERVICE_FILE not found."
fi

echo ""
read -r -p "🧹 Remove virtual environment (venv) and state cache (panel_state.json)? Source code and config.py will be kept [y/N]: " CLEAN_VENV
if [[ "$CLEAN_VENV" =~ ^[Yy]$ ]]; then
    rm -rf "$APP_DIR/venv" "$APP_DIR/panel_state.json" "$APP_DIR/panel_state.json.tmp"
    echo "✅ Virtual environment and state cache removed."
fi

echo "🎉 Uninstallation complete!"
