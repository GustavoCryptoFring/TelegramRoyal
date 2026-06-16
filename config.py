"""Configuration loaded from environment variables (optionally via .env)."""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DB_PATH = os.environ.get("DB_PATH", "rumble.db")

# Seconds of suspense between narrated rounds.
ROUND_DELAY = float(os.environ.get("ROUND_DELAY", "3"))
# Minimum players required for a game to actually start.
MIN_PLAYERS = int(os.environ.get("MIN_PLAYERS", "2"))
# Max allowed join-phase length in minutes.
MAX_MINUTES = int(os.environ.get("MAX_MINUTES", "1440"))
