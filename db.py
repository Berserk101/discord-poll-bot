# ── Database Layer (aiosqlite) ──
# Manages polls, options, and votes with async SQLite.

from __future__ import annotations

import aiosqlite
from config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS polls (
    poll_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id     INTEGER NOT NULL,
    channel_id   INTEGER NOT NULL,
    creator_id   INTEGER NOT NULL,
    title        TEXT    NOT NULL,
    max_picks    INTEGER NOT NULL DEFAULT 3,
    option_count INTEGER NOT NULL,
    header_msg_id  INTEGER,
    voting_msg_id  INTEGER,
    tally_msg_id   INTEGER,
    is_open      INTEGER NOT NULL DEFAULT 1,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS options (
    option_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id    INTEGER NOT NULL REFERENCES polls(poll_id) ON DELETE CASCADE,
    option_num INTEGER NOT NULL,
    label      TEXT,
    image_url  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS votes (
    vote_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id    INTEGER NOT NULL REFERENCES polls(poll_id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL,
    option_num INTEGER NOT NULL,
    voted_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(poll_id, user_id, option_num)
);
"""


async def init_db() -> None:
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()


# ── Poll CRUD ──

async def create_poll(
    guild_id: int,
    channel_id: int,
    creator_id: int,
    title: str,
    max_picks: int,
    option_count: int,
) -> int:
    """Insert a new poll and return its poll_id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO polls (guild_id, channel_id, creator_id, title, max_picks, option_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (guild_id, channel_id, creator_id, title, max_picks, option_count),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def add_options(poll_id: int, options: list[dict]) -> None:
    """Bulk-insert options. Each dict has keys: option_num, image_url, label (optional)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            "INSERT INTO options (poll_id, option_num, label, image_url) VALUES (?, ?, ?, ?)",
            [(poll_id, o["option_num"], o.get("label"), o["image_url"]) for o in options],
        )
        await db.commit()


async def save_message_ids(
    poll_id: int,
    header_msg_id: int,
    voting_msg_id: int,
    tally_msg_id: int,
) -> None:
    """Store Discord message IDs so we can edit them later."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE polls
               SET header_msg_id = ?, voting_msg_id = ?, tally_msg_id = ?
               WHERE poll_id = ?""",
            (header_msg_id, voting_msg_id, tally_msg_id, poll_id),
        )
        await db.commit()


async def get_poll(poll_id: int) -> dict | None:
    """Fetch a poll row as a dict."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM polls WHERE poll_id = ?", (poll_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_poll_options(poll_id: int) -> list[dict]:
    """Return all options for a poll, ordered by option_num."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM options WHERE poll_id = ? ORDER BY option_num", (poll_id,)
        )
        return [dict(r) for r in await cursor.fetchall()]


async def close_poll(poll_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE polls SET is_open = 0 WHERE poll_id = ?", (poll_id,))
        await db.commit()


async def delete_poll(poll_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM votes WHERE poll_id = ?", (poll_id,))
        await db.execute("DELETE FROM options WHERE poll_id = ?", (poll_id,))
        await db.execute("DELETE FROM polls WHERE poll_id = ?", (poll_id,))
        await db.commit()


# ── Voting ──

async def add_vote(poll_id: int, user_id: int, option_num: int, max_picks: int) -> bool:
    """
    Try to add a vote.  Returns True if successful, False if user already
    has max_picks votes (caller should show an ephemeral warning).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM votes WHERE poll_id = ? AND user_id = ?",
            (poll_id, user_id),
        )
        (count,) = await cursor.fetchone()  # type: ignore[misc]
        if count >= max_picks:
            return False

        await db.execute(
            "INSERT OR IGNORE INTO votes (poll_id, user_id, option_num) VALUES (?, ?, ?)",
            (poll_id, user_id, option_num),
        )
        await db.commit()
        return True


async def remove_vote(poll_id: int, user_id: int, option_num: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM votes WHERE poll_id = ? AND user_id = ? AND option_num = ?",
            (poll_id, user_id, option_num),
        )
        await db.commit()


async def get_user_votes(poll_id: int, user_id: int) -> set[int]:
    """Return the set of option_nums this user has voted for."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT option_num FROM votes WHERE poll_id = ? AND user_id = ?",
            (poll_id, user_id),
        )
        return {row[0] for row in await cursor.fetchall()}


async def get_tally(poll_id: int) -> dict[int, int]:
    """Return {option_num: vote_count} for every option (including 0-vote ones)."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Get total option count
        cursor = await db.execute(
            "SELECT option_count FROM polls WHERE poll_id = ?", (poll_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return {}
        option_count = row[0]

        # Count votes per option
        cursor = await db.execute(
            """SELECT option_num, COUNT(*) as cnt
               FROM votes WHERE poll_id = ?
               GROUP BY option_num""",
            (poll_id,),
        )
        tally = {i: 0 for i in range(1, option_count + 1)}
        for r in await cursor.fetchall():
            tally[r[0]] = r[1]
        return tally


async def get_total_voters(poll_id: int) -> int:
    """Return count of distinct voters."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM votes WHERE poll_id = ?", (poll_id,)
        )
        (count,) = await cursor.fetchone()  # type: ignore[misc]
        return count
