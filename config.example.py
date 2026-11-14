# Configuration template. Run ./install_service.sh for interactive setup
# or copy this file to config.py and fill in your credentials.

DISCORD_TOKEN = "YOUR_DISCORD_BOT_TOKEN"
PANEL_URL = "https://panel.example.com"
PANEL_API_KEY = "YOUR_CLIENT_API_KEY"
SERVER_ID = "YOUR_SERVER_SHORT_ID"

MC_HOST = "127.0.0.1"
MC_PORT = 25565

ALLOWED_USERS = {
    123456789012345678,
}

PANEL_TITLE = "Minecraft Server"
UPDATE_INTERVAL = 30
FORCE_REFRESH_INTERVAL = 300

RAM_STEP_MB = 100
CPU_STEP_PERCENT = 5
HTTP_TIMEOUT = 5.0
MC_TIMEOUT = 3.0
POWER_ACTION_DELAY = 2.0
