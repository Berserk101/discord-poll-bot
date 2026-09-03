# ── Discord Poll Bot Configuration ──

import os
from pathlib import Path

# ── Bot ──
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

# ── Poll limits ──
MAX_OPTIONS = 50       # hard cap on options per poll

# ── Paths ──
DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "polls.db"

# Ensure directories exist at import time
DATA_DIR.mkdir(exist_ok=True)
