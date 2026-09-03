# ── Discord Poll Bot — Entry Point ──
# A Polltab-style image poll bot for Discord.
# Run:  python bot.py
# Requires DISCORD_BOT_TOKEN environment variable.

from __future__ import annotations

import asyncio
import logging
import os
import sys

import discord
from discord.ext import commands

import db
from config import BOT_TOKEN

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger("pollbot")

# ── Intents ──
intents = discord.Intents.default()
intents.guilds = True


class PollBot(commands.Bot):
    """Custom Bot subclass so we can run setup in on_ready."""

    async def setup_hook(self) -> None:
        await db.init_db()
        log.info("Database initialised.")

        await self.load_extension("cogs.poll")
        log.info("Poll cog loaded.")

        # Sync slash commands globally (or to a specific guild for instant testing)
        synced = await self.tree.sync()
        log.info("Synced %d slash commands.", len(synced))


bot = PollBot(
    command_prefix="!",
    intents=intents,
    help_command=None,
)


@bot.event
async def on_ready() -> None:
    log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id if bot.user else "?")
    log.info("Serving %d guild(s).", len(bot.guilds))
    log.info("------")


def main() -> None:
    token = BOT_TOKEN
    if not token:
        log.error(
            "DISCORD_BOT_TOKEN environment variable is not set.\n"
            "Set it before running:  set DISCORD_BOT_TOKEN=your_token_here"
        )
        sys.exit(1)

    bot.run(token)


if __name__ == "__main__":
    main()
