# Harimine Bot — Discord bot for Minecraft & Pelican/Pterodactyl Panel
# Copyright (C) 2026 haribulus
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import json
import logging
import os
import sys
import time

import aiohttp
import discord
from discord import app_commands
from discord.ext import tasks
from mcstatus import JavaServer

log = logging.getLogger("harimine")

try:
    import config
except ImportError:
    sys.exit(
        "[Error]: config.py not found! "
        "Run ./install_service.sh or copy config.example.py to config.py."
    )

DISCORD_TOKEN = getattr(config, "DISCORD_TOKEN", "")
PANEL_URL = getattr(
    config, "PANEL_URL", getattr(config, "PELICAN_URL", "http://127.0.0.1")
).rstrip("/")
PANEL_API_KEY = getattr(
    config, "PANEL_API_KEY", getattr(config, "PELICAN_API_KEY", "")
)
SERVER_ID = getattr(config, "SERVER_ID", "")

MC_HOST = getattr(config, "MC_HOST", "127.0.0.1")
MC_PORT = int(getattr(config, "MC_PORT", 25565))
ALLOWED_USERS = set(getattr(config, "ALLOWED_USERS", set()))

PANEL_TITLE = getattr(config, "PANEL_TITLE", "Minecraft Server")
UPDATE_INTERVAL = max(5, int(getattr(config, "UPDATE_INTERVAL", 30)))
FORCE_REFRESH_INTERVAL = max(30, int(getattr(config, "FORCE_REFRESH_INTERVAL", 300)))
RAM_STEP_MB = max(1, int(getattr(config, "RAM_STEP_MB", 100)))
CPU_STEP_PERCENT = max(1, int(getattr(config, "CPU_STEP_PERCENT", 5)))
HTTP_TIMEOUT = float(getattr(config, "HTTP_TIMEOUT", 5.0))
MC_TIMEOUT = float(getattr(config, "MC_TIMEOUT", 3.0))
POWER_ACTION_DELAY = float(getattr(config, "POWER_ACTION_DELAY", 2.0))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "panel_state.json")

HEADERS = {
    "Authorization": f"Bearer {PANEL_API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}


def validate_config() -> None:
    placeholders = {"", "YOUR_DISCORD_BOT_TOKEN", "YOUR_CLIENT_API_KEY", "YOUR_SERVER_SHORT_ID"}
    if DISCORD_TOKEN in placeholders or PANEL_API_KEY in placeholders or SERVER_ID in placeholders:
        sys.exit(
            "[Error]: Missing required credentials in config.py "
            "(DISCORD_TOKEN, PANEL_API_KEY, or SERVER_ID)."
        )


def has_permission(interaction: discord.Interaction) -> bool:
    is_admin = interaction.permissions.administrator if interaction.guild else False
    return is_admin or (interaction.user.id in ALLOWED_USERS)


def format_uptime(uptime_ms: int) -> str:
    total_seconds = int(uptime_ms // 1000)
    if total_seconds < 60:
        return "< 1m"

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def save_panel_state(channel_id: int, message_id: int) -> None:
    tmp_file = f"{STATE_FILE}.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump({"channel_id": channel_id, "message_id": message_id}, f)
    os.replace(tmp_file, STATE_FILE)


def load_panel_state() -> dict | None:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def clear_panel_state() -> None:
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
        except OSError:
            pass


class ServerControlView(discord.ui.View):
    def __init__(self, bot_client: "HarimineBot"):
        super().__init__(timeout=None)
        self.bot = bot_client

    def update_buttons(self, state: str) -> None:
        self.start_button.disabled = state != "offline"
        self.restart_button.disabled = state != "running"
        self.stop_button.disabled = state not in ("running", "starting")

    @discord.ui.button(
        label="Start",
        style=discord.ButtonStyle.success,
        custom_id="mc_start_btn",
        emoji="▶️",
    )
    async def start_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not has_permission(interaction):
            await interaction.response.send_message(
                "⛔ You do not have permission to start the server.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        ok, msg = await self.bot.send_power_signal("start")
        await interaction.followup.send(msg, ephemeral=True)
        if ok:
            await asyncio.sleep(POWER_ACTION_DELAY)
            await self.bot.force_refresh_panel()

    @discord.ui.button(
        label="Restart",
        style=discord.ButtonStyle.primary,
        custom_id="mc_restart_btn",
        emoji="🔁",
    )
    async def restart_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not has_permission(interaction):
            await interaction.response.send_message(
                "⛔ You do not have permission to restart the server.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        ok, msg = await self.bot.send_power_signal("restart")
        await interaction.followup.send(msg, ephemeral=True)
        if ok:
            await asyncio.sleep(POWER_ACTION_DELAY)
            await self.bot.force_refresh_panel()

    @discord.ui.button(
        label="Stop",
        style=discord.ButtonStyle.danger,
        custom_id="mc_stop_btn",
        emoji="⏹️",
    )
    async def stop_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not has_permission(interaction):
            await interaction.response.send_message(
                "⛔ You do not have permission to stop the server.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        ok, msg = await self.bot.send_power_signal("stop")
        await interaction.followup.send(msg, ephemeral=True)
        if ok:
            await asyncio.sleep(POWER_ACTION_DELAY)
            await self.bot.force_refresh_panel()

    @discord.ui.button(
        label="Refresh",
        style=discord.ButtonStyle.secondary,
        custom_id="mc_status_btn",
        emoji="🔄",
    )
    async def status_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)
        await self.bot.force_refresh_panel()
        await interaction.followup.send("✅ Status updated.", ephemeral=True)


class HarimineBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.http_session: aiohttp.ClientSession | None = None
        self.mc_server = JavaServer(MC_HOST, MC_PORT, timeout=MC_TIMEOUT)
        self.control_view: ServerControlView | None = None

        self._panel_lock = asyncio.Lock()
        self._cached_partial_msg: discord.PartialMessage | None = None
        self._last_signature: tuple | None = None
        self._last_edit_ts: float = 0.0
        self._last_presence: str = ""

    async def setup_hook(self):
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        self.http_session = aiohttp.ClientSession(headers=HEADERS, timeout=timeout)
        self.control_view = ServerControlView(self)
        self.add_view(self.control_view)
        try:
            await self.tree.sync()
        except discord.HTTPException as e:
            log.warning("Failed to sync application commands: %s", e)
        self.update_status_task.start()

    async def close(self):
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        await super().close()

    async def get_server_resources(self) -> dict | None:
        if not self.http_session:
            return None
        url = f"{PANEL_URL}/api/client/servers/{SERVER_ID}/resources"
        try:
            async with self.http_session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("attributes")
                log.warning("Panel API returned status %s for resources", resp.status)
        except Exception as e:
            log.warning("Panel API request failed: %s", e)
        return None

    async def send_power_signal(self, signal: str) -> tuple[bool, str]:
        if not self.http_session:
            return False, "❌ HTTP session is not ready yet."
        url = f"{PANEL_URL}/api/client/servers/{SERVER_ID}/power"
        try:
            async with self.http_session.post(url, json={"signal": signal}) as resp:
                if resp.status == 204:
                    actions = {
                        "start": "🚀 Start signal sent! Server will be online in 20–30s.",
                        "restart": "🔁 Restart signal sent! Server will reboot in 20–40s.",
                        "stop": "🛑 Stop signal sent.",
                    }
                    return True, actions.get(signal, "Done.")
                return False, f"❌ Panel API returned HTTP {resp.status}."
        except Exception as e:
            return False, f"❌ Panel connection error: {e}"

    async def get_mc_players(self) -> tuple[int | None, int | None]:
        try:
            status = await self.mc_server.async_status()
            return status.players.online, status.players.max
        except Exception:
            return None, None

    async def build_status_embed(self) -> tuple[discord.Embed, str, tuple]:
        attrs = await self.get_server_resources()
        unix_now = int(time.time())

        if not attrs:
            if self.control_view:
                self.control_view.update_buttons("no_conn")
            embed = discord.Embed(
                title=PANEL_TITLE,
                description=f"⚠️ Cannot connect to the control panel.\nUpdated: <t:{unix_now}:R>",
                color=discord.Color.dark_grey(),
            )
            return embed, "Connection Error ⚠️", ("no_conn",)

        state = attrs.get("current_state", "offline")
        if self.control_view:
            self.control_view.update_buttons(state)

        res = attrs.get("resources", {})
        ram_mb = round(res.get("memory_bytes", 0) / (1024 * 1024))
        cpu = round(res.get("cpu_absolute", 0.0), 1)
        uptime_ms = res.get("uptime", 0)

        states_map = {
            "running": ("🟢 Online", discord.Color.green()),
            "starting": ("🟡 Starting...", discord.Color.gold()),
            "stopping": ("🟠 Stopping...", discord.Color.orange()),
            "offline": ("🔴 Offline", discord.Color.red()),
        }
        status_text, color = states_map.get(state, (state, discord.Color.light_grey()))

        embed = discord.Embed(title=PANEL_TITLE, color=color)
        embed.add_field(name="Status", value=status_text, inline=True)
        embed.add_field(name="Memory (RAM)", value=f"{ram_mb} MB", inline=True)
        embed.add_field(name="CPU Load", value=f"{cpu}%", inline=True)

        presence_text = "Minecraft: Offline 🔴"
        online = None

        if state == "running":
            online, max_p = await self.get_mc_players()
            if online is not None:
                embed.add_field(
                    name="Players Online",
                    value=f"**{online} / {max_p}**",
                    inline=True,
                )
                presence_text = f"Minecraft: {online}/{max_p} 🟢"
            else:
                embed.add_field(
                    name="Players Online", value="Loading world...", inline=True
                )
                presence_text = "Minecraft: Starting 🟡"

            if uptime_ms > 0:
                embed.add_field(
                    name="Uptime",
                    value=format_uptime(uptime_ms),
                    inline=True,
                )
        elif state == "starting":
            presence_text = "Minecraft: Starting 🟡"

        embed.add_field(name="Last Check", value=f"<t:{unix_now}:R>", inline=False)

        signature = (state, online, ram_mb // RAM_STEP_MB, int(cpu // CPU_STEP_PERCENT))
        return embed, presence_text, signature

    async def update_presence_safe(self, text: str) -> None:
        if text != self._last_presence:
            self._last_presence = text
            await self.change_presence(activity=discord.Game(name=text))

    async def get_target_message(self) -> discord.PartialMessage | None:
        if self._cached_partial_msg:
            return self._cached_partial_msg

        saved = load_panel_state()
        if not saved:
            return None

        try:
            channel = self.get_channel(saved["channel_id"]) or await self.fetch_channel(
                saved["channel_id"]
            )
            self._cached_partial_msg = channel.get_partial_message(saved["message_id"])
            return self._cached_partial_msg
        except (discord.NotFound, discord.Forbidden):
            log.info("Panel channel deleted or inaccessible. Clearing state.")
            clear_panel_state()
            return None
        except Exception as e:
            log.warning("Failed to fetch panel channel: %s", e)
            return None

    async def force_refresh_panel(self) -> None:
        self._last_signature = None
        await self._run_panel_cycle()

    async def _run_panel_cycle(self) -> None:
        async with self._panel_lock:
            embed, presence_text, signature = await self.build_status_embed()
            await self.update_presence_safe(presence_text)
            now = time.monotonic()

            if (
                signature == self._last_signature
                and (now - self._last_edit_ts) < FORCE_REFRESH_INTERVAL
            ):
                return

            target_msg = await self.get_target_message()
            if not target_msg:
                return

            try:
                await target_msg.edit(embed=embed, view=self.control_view)
                self._last_signature = signature
                self._last_edit_ts = now
            except discord.NotFound:
                log.info("Panel message was deleted in Discord. Clearing cache.")
                self._cached_partial_msg = None
                clear_panel_state()
            except Exception as e:
                log.warning("Failed to update panel message: %s", e)
                self._cached_partial_msg = None

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def update_status_task(self):
        await self._run_panel_cycle()

    @update_status_task.before_loop
    async def before_update(self):
        await self.wait_until_ready()


bot = HarimineBot()


@bot.tree.command(
    name="panel", description="Create a live server control panel in the current channel"
)
@app_commands.guild_only()
async def panel_command(interaction: discord.Interaction):
    if not has_permission(interaction):
        await interaction.response.send_message(
            "⛔ You do not have permission to create the control panel.", ephemeral=True
        )
        return

    await interaction.response.defer()
    async with bot._panel_lock:
        embed, presence_text, signature = await bot.build_status_embed()
        msg = await interaction.followup.send(
            embed=embed, view=bot.control_view, wait=True
        )
        save_panel_state(interaction.channel_id, msg.id)
        bot._cached_partial_msg = self.get_partial_messageable(
            interaction.channel_id
        ).get_partial_message(msg.id) if hasattr(self := bot, "get_partial_messageable") else interaction.channel.get_partial_message(msg.id)
        bot._last_signature = signature
        bot._last_edit_ts = time.monotonic()
        await bot.update_presence_safe(presence_text)


if __name__ == "__main__":
    validate_config()
    bot.run(DISCORD_TOKEN)
