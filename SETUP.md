# 🛠 Harimine Bot — Detailed Setup Guide

Step-by-step instructions for creating a Discord bot application and obtaining Client API credentials from **Pelican**, **Pterodactyl**, **Jexactyl**, or **Pyrodactyl**.

---

## 1. Creating and Inviting the Discord Bot

### Step 1.1. Create the Application & Get the Token
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and click **New Application**.
2. Open the **Bot** tab in the left sidebar.
3. Click **Reset Token** (or **View Token**), confirm, and copy the token — this is your `DISCORD_TOKEN`.
   *(No Privileged Gateway Intents are required).*

### Step 1.2. Invite the Bot to Your Discord Server
1. Open **OAuth2** -> **URL Generator** in the left sidebar.
2. Under **SCOPES**, check:
   * `bot`
   * `applications.commands` (required for the `/panel` slash command)
3. Under **BOT PERMISSIONS**, check:
   * `View Channels`
   * `Send Messages`
   * `Embed Links`
   * `Read Message History`
4. Copy the **Generated URL** at the bottom, open it in your browser, and authorize the bot on your server.

### Step 1.3. Find Your Discord User ID (for `ALLOWED_USERS`)
1. In Discord Settings, go to **Advanced** and enable **Developer Mode**.
2. Right-click your profile (or any trusted user's profile) and select **Copy User ID**.

---

## 2. Getting Panel API Credentials (Pelican / Pterodactyl)

1. Log in to your server control panel, open your profile settings (**Account** -> **API Credentials**).
2. Generate a new **Client API Key** and copy it (starts with `plcn_...` in Pelican or `ptlc_...` in Pterodactyl) — this is your `PANEL_API_KEY`.
3. Open your Minecraft server page in the panel:
   * Copy the short 8-character identifier from the browser URL (e.g., `1a2b3c4d` in `.../server/1a2b3c4d`) or from **Settings** -> **Debug Information** — this is your `SERVER_ID`.

---

## 3. Configuration Reference (`config.py`)

When running `./install_service.sh` (or the `curl | bash` one-liner), `config.py` is generated interactively. You can also create or edit it manually (`cp config.example.py config.py`).

| Variable | Default | Description |
|---|---|---|
| `DISCORD_TOKEN` | — | Your Discord Bot token |
| `PANEL_URL` | `http://127.0.0.1` | Base URL of your Pelican/Pterodactyl panel (no trailing slash) |
| `PANEL_API_KEY` | — | Client API key (`plcn_...` or `ptlc_...`) |
| `SERVER_ID` | — | Short server identifier from the panel |
| `MC_HOST` / `MC_PORT` | `127.0.0.1` / `25565` | Minecraft server IP and port for querying online player count |
| `ALLOWED_USERS` | `set()` | Set of Discord User IDs allowed to control power states |
| `PANEL_TITLE` | `Minecraft Server` | Title of the Discord status embed |
| `UPDATE_INTERVAL` | `30` | Background status poll interval in seconds |
| `FORCE_REFRESH_INTERVAL` | `300` | Forced Discord message refresh interval in seconds when idle |
| `RAM_STEP_MB` | `100` | RAM change threshold (MB) required to trigger a message edit |
| `CPU_STEP_PERCENT` | `5` | CPU change threshold (%) required to trigger a message edit |
| `HTTP_TIMEOUT` | `5.0` | Panel API HTTP request timeout in seconds |
| `MC_TIMEOUT` | `3.0` | Minecraft server ping timeout in seconds |
| `POWER_ACTION_DELAY` | `2.0` | Delay in seconds before refreshing the panel after a power action |
