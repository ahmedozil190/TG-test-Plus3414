import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta

import phonenumbers
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from uvicorn import Config, Server

from config import BOT_TOKEN, SELLER_BOT_TOKEN
from database.engine import init_db, async_session
from database.models import Account, AccountStatus, CountryPrice, User, Transaction, TransactionType
from sqlalchemy import select
from handlers import main_router
from web_admin import app
from middlewares.user_update import UserUpdateMiddleware

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def auto_approve_task(bot_seller: Bot):
    """Background task to automatically approve pending accounts after delay."""
    logger.info("Starting Auto-Approve background task...")
    while True:
        try:
            async with async_session() as session:
                stmt = select(Account).where(Account.status == AccountStatus.PENDING)
                pending_accs = (await session.execute(stmt)).scalars().all()
                
                for acc in pending_accs:
                    try:
                        p = phonenumbers.parse(acc.phone_number)
                        country_code = str(p.country_code)
                        
                        cp_stmt = select(CountryPrice).where(CountryPrice.country_code == country_code)
                        cp = (await session.execute(cp_stmt)).scalar()
                        if not cp: continue
                        
                        delay_delta = timedelta(seconds=cp.approve_delay)
                        if datetime.utcnow() >= (acc.created_at + delay_delta):
                            # Auto-Approve!
                            acc.status = AccountStatus.AVAILABLE
                            acc.price = cp.price # Set the selling price
                            
                            # Pay the seller
                            seller = await session.get(User, acc.seller_id)
                            if seller:
                                seller.balance_sourcing += cp.buy_price
                                tx = Transaction(user_id=seller.id, type=TransactionType.SELL, amount=cp.buy_price)
                                session.add(tx)
                                
                                # Notify via seller bot
                                try:
                                    await bot_seller.send_message(
                                        seller.id,
                                        f"✅ **تمت الموافقة التلقائية!**\n\n"
                                        f"رقم: `{acc.phone_number}` أصبح متاحاً الآن.\n"
                                        f"💰 تم إضافة **${cp.buy_price}** لرصيدك.\n"
                                        f"استمر في التوريد وجني الأرباح! 💸",
                                        parse_mode="Markdown"
                                    )
                                except Exception as n_err:
                                    logger.error(f"Failed to notify seller {seller.id}: {n_err}")
                    except Exception as item_err:
                        logger.error(f"Error processing pending account {acc.id}: {item_err}")
                
                await session.commit()
        except Exception as e:
            logger.error(f"Auto-approve loop error: {e}")
        
        await asyncio.sleep(60)

from handlers.seller import seller_router

async def start_bot_service(dp: Dispatcher, bot: Bot, name: str):
    """Safely starts a bot service."""
    try:
        me = await bot.get_me()
        logger.info(f"✅ SUCCESS: {name} Bot (@{me.username}) is connected and starting!")
        
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ FATAL ERROR in {name} Bot connection: {e}")

async def main():
    logger.info("Initializing Dual-Bot Ecosystem...")
    
    # 1. Database
    try:
        await init_db()
        logger.info("Database initialized.")
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        return

    # 2. Setup Bots
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN missing!")
        return
        
    # Buyer Bot
    bot_buyer = Bot(token=BOT_TOKEN)
    dp_buyer = Dispatcher()
    dp_buyer.include_router(main_router)
    
    # Register middleware
    dp_buyer.update.outer_middleware(UserUpdateMiddleware(bot_type="store"))

    # Seller Bot (Optional token)
    bot_seller = None
    if SELLER_BOT_TOKEN:
        try:
            bot_seller = Bot(token=SELLER_BOT_TOKEN)
            dp_seller = Dispatcher()
            dp_seller.include_router(seller_router)
            
            # Register middleware
            dp_seller.update.outer_middleware(UserUpdateMiddleware(bot_type="sourcing"))
            
            logger.info("Seller Bot configured.")
        except Exception as e:
            logger.error(f"Seller Bot configuration failed: {e}")
            bot_seller = None
    # 3. Attach bots to app state for Web Admin panel access
    app.state.bot_buyer = bot_buyer
    app.state.bot_seller = bot_seller
    
    # 4. Web Server Task
    port = int(os.environ.get("PORT", 8000))
    config = Config(app=app, host="0.0.0.0", port=port, log_level="info")
    server = Server(config)
    web_task = asyncio.create_task(server.serve())
    logger.info(f"Web Admin Panel task created on port {port}.")

    # 4. Background Helper Tasks
    tasks = [web_task]
    
    # 5. Main Polling (Buyer Bot)
    # 5. Set Bot Commands (Side Menu)
    from aiogram.types import BotCommandScopeAllPrivateChats
    
    buyer_commands = [BotCommand(command="start", description="/start")]
    seller_commands = [
        BotCommand(command="start", description="/start"),
        BotCommand(command="coin", description="/coin"),
        BotCommand(command="cancel", description="/cancel"),
        BotCommand(command="language", description="/language"),
        BotCommand(command="cap", description="/cap")
    ]

    try:
        await bot_buyer.set_my_commands(buyer_commands, scope=BotCommandScopeAllPrivateChats())
        logger.info("Buyer Bot commands set.")
        if bot_seller:
            await bot_seller.set_my_commands(seller_commands, scope=BotCommandScopeAllPrivateChats())
            logger.info("Seller Bot commands set.")
    except Exception as e:
        logger.error(f"Failed to set commands: {e}")

    # 6. Start Polling Tasks
    tasks.append(asyncio.create_task(start_bot_service(dp_buyer, bot_buyer, "Store/Buyer")))
    
    if bot_seller:
        tasks.append(asyncio.create_task(auto_approve_task(bot_seller)))
        tasks.append(asyncio.create_task(start_bot_service(dp_seller, bot_seller, "Seller/Sourcing")))

    # Wait for completion or keep running
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
