#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/haribulus/harimine-bot.git"
DEFAULT_INSTALL_DIR="/opt/harimine-bot"
SERVICE_NAME="harimine-bot"

if [ -n "$SUDO_USER" ]; then
    APP_USER="$SUDO_USER"
    APP_GROUP="$(id -gn "$SUDO_USER")"
else
    APP_USER="$(whoami)"
    APP_GROUP="$(id -gn)"
fi

install_sys_deps() {
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y -qq git python3 python3-venv python3-pip
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y -q git python3 python3-pip
    elif command -v pacman &>/dev/null; then
        sudo pacman -Sy --noconfirm --needed git python python-pip
    else
        echo "❌ Error: git or python3-venv is missing. Please install them manually."
        exit 1
    fi
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd || pwd)"
if [ -f "$SCRIPT_DIR/bot.py" ] && [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    APP_DIR="$SCRIPT_DIR"
else
    echo "🌐 Starting Harimine Bot network installation..."
    read -r -p "📂 Installation directory [default: ${DEFAULT_INSTALL_DIR}]: " CUSTOM_DIR < /dev/tty
    APP_DIR="${CUSTOM_DIR:-$DEFAULT_INSTALL_DIR}"

    if ! command -v git &>/dev/null || ! python3 -m venv --help &>/dev/null; then
        echo "📦 Installing required system packages (git, python3-venv)..."
        install_sys_deps
    fi

    if [ ! -d "$APP_DIR" ]; then
        sudo mkdir -p "$APP_DIR"
        sudo chown "$APP_USER:$APP_GROUP" "$APP_DIR"
    fi

    if [ -d "$APP_DIR/.git" ]; then
        echo "🔄 Existing repository found, pulling latest changes..."
        sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only
    else
        echo "📥 Cloning repository from $REPO_URL to $APP_DIR..."
        sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR"
    fi
fi

cd "$APP_DIR"
echo "🔧 Configuring project in: $APP_DIR"
echo "👤 Service user: $APP_USER ($APP_GROUP)"

NEED_CONFIG=false
if [ ! -f "$APP_DIR/config.py" ] || grep -qE "YOUR_DISCORD_BOT_TOKEN|YOUR_CLIENT_API_KEY" "$APP_DIR/config.py" 2>/dev/null; then
    NEED_CONFIG=true
else
    read -r -p "ℹ️ config.py already exists. Reconfigure from scratch? [y/N]: " RECONFIG < /dev/tty
    if [[ "$RECONFIG" =~ ^[Yy]$ ]]; then
        NEED_CONFIG=true
    fi
fi

if [ "$NEED_CONFIG" = true ]; then
    echo ""
    echo "📝 === Harimine Bot Configuration Wizard ==="

    while [ -z "$INPUT_DISCORD_TOKEN" ]; do
        read -r -p "1. Enter DISCORD_TOKEN (required): " INPUT_DISCORD_TOKEN < /dev/tty
    done

    read -r -p "2. Enter Panel URL [default: http://127.0.0.1]: " INPUT_PANEL_URL < /dev/tty
    INPUT_PANEL_URL="${INPUT_PANEL_URL:-http://127.0.0.1}"
    INPUT_PANEL_URL="${INPUT_PANEL_URL%/}"

    while [ -z "$INPUT_PANEL_KEY" ]; do
        read -r -p "3. Enter PANEL_API_KEY / Client API Key (required): " INPUT_PANEL_KEY < /dev/tty
    done

    while [ -z "$INPUT_SERVER_ID" ]; do
        read -r -p "4. Enter SERVER_ID from panel (required): " INPUT_SERVER_ID < /dev/tty
    done

    DEFAULT_MC_HOST="$(echo "$INPUT_PANEL_URL" | sed -E 's|^https?://||; s|:[0-9]+.*||; s|/.*||')"
    DEFAULT_MC_HOST="${DEFAULT_MC_HOST:-127.0.0.1}"

    read -r -p "5. Enter Minecraft server IP MC_HOST [default: ${DEFAULT_MC_HOST}]: " INPUT_MC_HOST < /dev/tty
    INPUT_MC_HOST="${INPUT_MC_HOST:-$DEFAULT_MC_HOST}"

    while true; do
        read -r -p "6. Enter Minecraft server port MC_PORT [default: 25565]: " INPUT_MC_PORT < /dev/tty
        INPUT_MC_PORT="${INPUT_MC_PORT:-25565}"
        [[ "$INPUT_MC_PORT" =~ ^[0-9]+$ ]] && break
        echo "⚠️ Port must be a number."
    done

    read -r -p "7. Enter allowed Discord User IDs (space or comma separated): " INPUT_USERS < /dev/tty

    read -r -p "8. Enter embed PANEL_TITLE [default: Minecraft Server]: " INPUT_TITLE < /dev/tty
    INPUT_TITLE="${INPUT_TITLE:-Minecraft Server}"

    while true; do
        read -r -p "9. Enter status poll UPDATE_INTERVAL in seconds [default: 30]: " INPUT_INTERVAL < /dev/tty
        INPUT_INTERVAL="${INPUT_INTERVAL:-30}"
        [[ "$INPUT_INTERVAL" =~ ^[0-9]+$ ]] && break
        echo "⚠️ Interval must be a number."
    done

    # Safely serialize config.py via Python to prevent shell/quote injection
    env \
        CFG_PATH="$APP_DIR/config.py" \
        CFG_TOKEN="$INPUT_DISCORD_TOKEN" \
        CFG_URL="$INPUT_PANEL_URL" \
        CFG_KEY="$INPUT_PANEL_KEY" \
        CFG_SID="$INPUT_SERVER_ID" \
        CFG_HOST="$INPUT_MC_HOST" \
        CFG_PORT="$INPUT_MC_PORT" \
        CFG_USERS="$INPUT_USERS" \
        CFG_TITLE="$INPUT_TITLE" \
        CFG_INT="$INPUT_INTERVAL" \
        python3 -c '
import os, re

uids = [int(x) for x in re.split(r"[\s,]+", os.environ["CFG_USERS"].strip()) if x.isdigit()]
users_str = "{\n" + "".join(f"    {u},\n" for u in uids) + "}" if uids else "set()"

content = f"""# Local configuration file (auto-generated, DO NOT commit to Git!)

DISCORD_TOKEN = {os.environ["CFG_TOKEN"]!r}
PANEL_URL = {os.environ["CFG_URL"]!r}
PANEL_API_KEY = {os.environ["CFG_KEY"]!r}
SERVER_ID = {os.environ["CFG_SID"]!r}

MC_HOST = {os.environ["CFG_HOST"]!r}
MC_PORT = {int(os.environ["CFG_PORT"])}

ALLOWED_USERS = {users_str}

PANEL_TITLE = {os.environ["CFG_TITLE"]!r}
UPDATE_INTERVAL = {int(os.environ["CFG_INT"])}
FORCE_REFRESH_INTERVAL = 300

RAM_STEP_MB = 100
CPU_STEP_PERCENT = 5
HTTP_TIMEOUT = 5.0
MC_TIMEOUT = 3.0
POWER_ACTION_DELAY = 2.0
"""
with open(os.environ["CFG_PATH"], "w", encoding="utf-8") as f:
    f.write(content)
'

    sudo chown "$APP_USER:$APP_GROUP" "$APP_DIR/config.py"
    sudo chmod 600 "$APP_DIR/config.py"
    echo "✅ config.py created and secured (chmod 600)."
    echo ""
fi

if [ ! -d "$APP_DIR/venv" ]; then
    echo "🐍 Creating Python virtual environment (venv)..."
    sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
else
    echo "ℹ️ Virtual environment venv already exists."
fi

echo "📦 Installing Python dependencies..."
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip -q
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q
echo "✅ Dependencies installed."

SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
echo "⚙️ Creating systemd service: $SERVICE_FILE"

sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Harimine Discord Bot (Pelican/Pterodactyl & Minecraft Status)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/venv/bin/python ${APP_DIR}/bot.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo "🚀 Starting $SERVICE_NAME service..."
sudo systemctl restart "$SERVICE_NAME"
sleep 2
sudo systemctl status "$SERVICE_NAME" --no-pager
