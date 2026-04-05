import asyncio
import logging
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from database.engine import init_db
from handlers import main_router

logging.basicConfig(level=logging.INFO)

async def main():
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN is not set in .env")
        return

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(main_router)
    
    logging.info("Initializing database...")
    await init_db()
    
    logging.info("Starting Web Admin Panel...")
    from uvicorn import Config, Server
    from web_admin import app
    import os
    port = int(os.environ.get("PORT", 8000))
    config = Config(app=app, host="0.0.0.0", port=port, log_level="info")
    server = Server(config)
    asyncio.create_task(server.serve())
    
    logging.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
