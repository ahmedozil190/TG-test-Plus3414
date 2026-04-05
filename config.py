import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
API_ID = os.getenv("API_ID", "0")
API_ID = int(API_ID) if API_ID.isdigit() else 0
API_HASH = os.getenv("API_HASH", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///app.db")
