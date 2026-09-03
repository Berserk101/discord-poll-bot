# ── Poll Cog — Commands & Interactive UI ──
# Each photo is posted as its own message with a Vote/Unvote button.
# Results are hidden until the poll is closed, then top 10 are shown.

from __future__ import annotations

import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

import db
from config import MAX_OPTIONS

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Imgur URL Fixer
# ─────────────────────────────────────────────

def _fix_image_url(url: str) -> str:
    """
    Convert common image hosting URLs to direct-image URLs that
    Discord can embed.  Covers the main Imgur pitfalls:

      imgur.com/XYZ        -> i.imgur.com/XYZ.jpg
      i.imgur.com/XYZ      -> i.imgur.com/XYZ.jpg   (add extension)
      imgur.com/a/ALBUM    -> unchanged (can't embed albums)
    """
    # ── Imgur gallery page -> direct link ──
    # e.g. https://imgur.com/abc123  (no /a/ or /gallery/)
    m = re.match(
        r"https?://(?:www\.)?imgur\.com/(?!a/|gallery/)([A-Za-z0-9]+)(?:\.[a-z]+)?$",
        url,
    )
    if m:
        img_id = m.group(1)
        return f"https://i.imgur.com/{img_id}.jpg"

    # ── i.imgur.com without extension ──
    m = re.match(
        r"https?://i\.imgur\.com/([A-Za-z0-9]+)$",
        url,
    )
    if m:
        img_id = m.group(1)
        return f"https://i.imgur.com/{img_id}.jpg"

    return url


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _bar(count: int, max_count: int, width: int = 12) -> str:
    if max_count == 0:
        return "░" * width
    filled = round(count / max_count * width)
    return "█" * filled + "░" * (width - filled)


def _build_winners_embed(
    title: str,
    tally: dict[int, int],
    total_voters: int,
    options: list[dict] | None = None,
) -> discord.Embed:
    """Build a TOP 10 winners embed for a closed poll."""
    max_count = max(tally.values()) if tally else 0
    sorted_opts = sorted(tally.items(), key=lambda kv: kv[1], reverse=True)

    # Only top 10
    top10 = sorted_opts[:10]

    lines: list[str] = []
    for rank, (opt_num, count) in enumerate(top10, start=1):
        label = ""
        if options:
            match = [o for o in options if o["option_num"] == opt_num]
            if match and match[0].get("label"):
                label = f" {match[0]['label']}"

        bar = _bar(count, max_count)

        # Medal emoji for top 3
        if rank == 1:
            medal = " :first_place:"
        elif rank == 2:
            medal = " :second_place:"
        elif rank == 3:
            medal = " :third_place:"
        else:
            medal = ""

        lines.append(
            f"**{rank}.** Option #{opt_num}{label}  {bar}  **{count}** votes{medal}"
        )

    description = "\n".join(lines) if lines else "*No votes were cast.*"

    embed = discord.Embed(
        title=f"WINNERS  --  {title}",
        description=description,
        color=discord.Color.gold(),
    )
    embed.set_footer(text=f"Total voters: {total_voters}  |  Poll CLOSED  |  Top 10 shown")
    return embed


# ─────────────────────────────────────────────
#  Single-Photo Vote Button
# ─────────────────────────────────────────────

class VoteView(discord.ui.View):
    """A single Vote/Unvote button attached to one photo message."""

    def __init__(self, poll_id: int, option_num: int, max_picks: int, is_open: bool = True):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.option_num = option_num
        self.max_picks = max_picks

        btn = discord.ui.Button(
            label=f"Vote #{option_num}",
            style=discord.ButtonStyle.success,
            custom_id=f"pollvote_{poll_id}_{option_num}",
            disabled=not is_open,
        )
        btn.callback = self.vote_callback
        self.add_item(btn)

    async def vote_callback(self, interaction: discord.Interaction) -> None:
        # Check if poll is still open
        poll = await db.get_poll(self.poll_id)
        if poll is None or not poll["is_open"]:
            await interaction.response.send_message(
                "This poll is closed.", ephemeral=True
            )
            return

        user_id = interaction.user.id
        user_votes = await db.get_user_votes(self.poll_id, user_id)

        if self.option_num in user_votes:
            # ── Un-vote ──
            await db.remove_vote(self.poll_id, user_id, self.option_num)
            user_votes.discard(self.option_num)
            await interaction.response.send_message(
                f"Removed your vote for **#{self.option_num}**. "
                f"({len(user_votes)}/{self.max_picks} picks used)",
                ephemeral=True,
            )
        else:
            # ── Vote ──
            success = await db.add_vote(
                self.poll_id, user_id, self.option_num, self.max_picks
            )
            if not success:
                await interaction.response.send_message(
                    f"You've already picked **{self.max_picks}**! "
                    f"Unselect one first by clicking its Vote button again.",
                    ephemeral=True,
                )
                return
            user_votes.add(self.option_num)
            await interaction.response.send_message(
                f"Voted for **#{self.option_num}**! "
                f"({len(user_votes)}/{self.max_picks} picks used)",
                ephemeral=True,
            )


# ─────────────────────────────────────────────
#  Cog
# ─────────────────────────────────────────────

class PollCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /createpoll ──

    @app_commands.command(
        name="createpoll",
        description="Create an image poll (attach a .txt with one image URL per line)",
    )
    @app_commands.describe(
        title="Poll title",
        max_picks="Max selections per voter (default 3)",
        images="A .txt file with one image URL per line",
    )
    async def createpoll(
        self,
        interaction: discord.Interaction,
        title: str,
        images: discord.Attachment,
        max_picks: int = 3,
    ) -> None:
        await interaction.response.defer(thinking=True)

        # ── Validate ──
        if not images.filename.endswith(".txt"):
            await interaction.followup.send(
                "Please attach a `.txt` file with one image URL per line.",
                ephemeral=True,
            )
            return

        raw = (await images.read()).decode("utf-8", errors="ignore")
        urls = [
            line.strip()
            for line in raw.splitlines()
            if line.strip() and line.strip().startswith("http")
        ]

        if not urls:
            await interaction.followup.send("No valid URLs found in the file.", ephemeral=True)
            return
        if len(urls) > MAX_OPTIONS:
            await interaction.followup.send(
                f"Too many options ({len(urls)}). Max is {MAX_OPTIONS}.",
                ephemeral=True,
            )
            return
        if max_picks < 1:
            max_picks = 1
        if max_picks > len(urls):
            max_picks = len(urls)

        # ── Fix image URLs ──
        urls = [_fix_image_url(u) for u in urls]

        # ── Create poll in DB ──
        poll_id = await db.create_poll(
            guild_id=interaction.guild_id or 0,
            channel_id=interaction.channel_id or 0,
            creator_id=interaction.user.id,
            title=title,
            max_picks=max_picks,
            option_count=len(urls),
        )

        options_data = [
            {"option_num": i + 1, "image_url": url, "label": None}
            for i, url in enumerate(urls)
        ]
        await db.add_options(poll_id, options_data)

        channel = interaction.channel

        # ── Header message ──
        header_embed = discord.Embed(
            title=f"Poll: {title}",
            description=(
                f"**{len(urls)} photos below** -- scroll through and vote!\n"
                f"Pick up to **{max_picks}**. Click the Vote button to vote, "
                f"click it again to unvote."
            ),
            color=discord.Color.gold(),
        )
        header_embed.set_footer(text=f"Poll #{poll_id}")
        await channel.send(embed=header_embed)  # type: ignore[union-attr]

        # ── Send each photo as its own message ──
        for i, url in enumerate(urls):
            option_num = i + 1
            embed = discord.Embed(
                title=f"#{option_num}",
                color=discord.Color.dark_grey(),
            )
            embed.set_image(url=url)

            view = VoteView(
                poll_id=poll_id,
                option_num=option_num,
                max_picks=max_picks,
                is_open=True,
            )
            await channel.send(embed=embed, view=view)  # type: ignore[union-attr]

        # No tally message — results hidden until close
        await db.save_message_ids(poll_id, 0, 0, 0)

        await interaction.followup.send(
            f"Poll **#{poll_id}** created with **{len(urls)}** photos! "
            f"Results will be revealed when you run `/closepoll {poll_id}`.",
            ephemeral=True,
        )

    # ── /closepoll ──

    @app_commands.command(name="closepoll", description="Close a poll and reveal the top 10 winners")
    @app_commands.describe(poll_id="The poll ID to close")
    async def closepoll(self, interaction: discord.Interaction, poll_id: int) -> None:
        poll = await db.get_poll(poll_id)
        if poll is None:
            await interaction.response.send_message("Poll not found.", ephemeral=True)
            return
        if (
            poll["creator_id"] != interaction.user.id
            and not interaction.user.guild_permissions.administrator  # type: ignore[union-attr]
        ):
            await interaction.response.send_message(
                "Only the poll creator or an admin can close this.", ephemeral=True
            )
            return
        if not poll["is_open"]:
            await interaction.response.send_message(
                "This poll is already closed.", ephemeral=True
            )
            return

        await db.close_poll(poll_id)

        # Build and post the top 10 winners
        tally = await db.get_tally(poll_id)
        total_voters = await db.get_total_voters(poll_id)
        options = await db.get_poll_options(poll_id)

        embed = _build_winners_embed(
            title=poll["title"],
            tally=tally,
            total_voters=total_voters,
            options=options,
        )
        await interaction.response.send_message(embed=embed)

    # ── /myvotes ──

    @app_commands.command(name="myvotes", description="See your current votes in a poll")
    @app_commands.describe(poll_id="The poll ID")
    async def myvotes(self, interaction: discord.Interaction, poll_id: int) -> None:
        poll = await db.get_poll(poll_id)
        if poll is None:
            await interaction.response.send_message("Poll not found.", ephemeral=True)
            return

        user_votes = await db.get_user_votes(poll_id, interaction.user.id)
        if not user_votes:
            await interaction.response.send_message(
                "You haven't voted in this poll yet.", ephemeral=True
            )
            return

        sorted_votes = sorted(user_votes)
        await interaction.response.send_message(
            f"Your votes in **{poll['title']}**: "
            + ", ".join(f"`#{v}`" for v in sorted_votes),
            ephemeral=True,
        )

    # ── /deletepoll ──

    @app_commands.command(name="deletepoll", description="Delete a poll and all its data")
    @app_commands.describe(poll_id="The poll ID to delete")
    async def deletepoll(self, interaction: discord.Interaction, poll_id: int) -> None:
        poll = await db.get_poll(poll_id)
        if poll is None:
            await interaction.response.send_message("Poll not found.", ephemeral=True)
            return
        if (
            poll["creator_id"] != interaction.user.id
            and not interaction.user.guild_permissions.administrator  # type: ignore[union-attr]
        ):
            await interaction.response.send_message(
                "Only the poll creator or an admin can delete this.", ephemeral=True
            )
            return

        await db.delete_poll(poll_id)
        await interaction.response.send_message(
            f"Poll **#{poll_id}** deleted.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PollCog(bot))
