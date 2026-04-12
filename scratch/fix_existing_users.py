import asyncio
import logging
from aiogram import Bot
from database.engine import async_session
from database.models import User
from sqlalchemy import select
from config import BOT_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def backfill_users():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing!")
        return

    bot = Bot(token=BOT_TOKEN)
    logger.info("Starting backfill for users with missing details...")

    async with async_session() as session:
        # Fetch users with missing full name or username
        stmt = select(User).where((User.full_name == None) | (User.username == None))
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        logger.info(f"Found {len(users)} users to process.")
        
        for user in users:
            try:
                # Use get_chat to fetch member info
                chat = await bot.get_chat(user.id)
                
                full_name = f"{chat.first_name or ''} {chat.last_name or ''}".strip() or "N/A"
                username = chat.username or "N/A"
                
                user.full_name = full_name
                user.username = username
                
                logger.info(f"Updated user {user.id}: {full_name} (@{username})")
                
                # Small sleep to respect rate limits
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed to fetch info for user {user.id}: {e}")
                # Set to "N/A" string so they aren't processed again by this query
                user.full_name = "User (Not Found)"
                user.username = "Unknown"
        
        await session.commit()
    
    await bot.session.close()
    logger.info("Backfill completed.")

if __name__ == "__main__":
    asyncio.run(backfill_users())
