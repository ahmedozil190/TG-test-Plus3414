import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
API_ID = os.getenv("API_ID", "0")
API_ID = int(API_ID) if API_ID.isdigit() else 0
API_HASH = os.getenv("API_HASH", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

# Database
# For Railway persistence, we check if /data volume exists
if os.path.exists("/data"):
    DATABASE_URL = "sqlite+aiosqlite:////data/app.db"
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///app.db")

# WebApp URLs
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://web-production-5e98a.up.railway.app")
STORE_URL = f"{WEBAPP_URL}/store"
