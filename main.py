import asyncio
import logging
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from config import BOT_TOKEN
from database.engine import init_db
from handlers import main_router

logging.basicConfig(level=logging.INFO)

from datetime import datetime, timedelta
import phonenumbers

async def auto_approve_task(bot_seller: Bot):
    """Background task to automatically approve pending accounts after delay."""
    logging.info("Auto-approve task started.")
    while True:
        try:
            async with async_session() as session:
                from database.models import Account, AccountStatus, CountryPrice, User, Transaction, TransactionType
                from sqlalchemy import select
                
                stmt = select(Account).where(Account.status == AccountStatus.PENDING)
                pending_accs = (await session.execute(stmt)).scalars().all()
                
                for acc in pending_accs:
                    try:
                        p = phonenumbers.parse(acc.phone_number)
                        country_code = str(p.country_code)
                        
                        cp_stmt = select(CountryPrice).where(CountryPrice.country_code == country_code)
                        cp = (await session.execute(cp_stmt)).scalar()
                        if not cp: continue
                        
                        delay_delta = timedelta(minutes=cp.approve_delay)
                        if datetime.utcnow() >= (acc.created_at + delay_delta):
                            # Auto-Approve!
                            acc.status = AccountStatus.AVAILABLE
                            acc.price = cp.price # Set the selling price
                            
                            # Pay the seller
                            seller = await session.get(User, acc.seller_id)
                            if seller:
                                seller.balance += cp.buy_price
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
                                    logging.error(f"Failed to notify seller {seller.id}: {n_err}")
                    except Exception as item_err:
                        logging.error(f"Error processing pending account {acc.id}: {item_err}")
                
                await session.commit()
        except Exception as e:
            logging.error(f"Auto-approve loop error: {e}")
        
        await asyncio.sleep(60) # Check every minute

async def main():
    if not BOT_TOKEN or not SELLER_BOT_TOKEN:
        logging.error("BOT_TOKEN or SELLER_BOT_TOKEN is not set in .env")
        return

    # Buyer Bot (Store)
    bot_buyer = Bot(token=BOT_TOKEN)
    dp_buyer = Dispatcher()
    dp_buyer.include_router(main_router)

    # Seller Bot (Sourcing)
    bot_seller = Bot(token=SELLER_BOT_TOKEN)
    dp_seller = Dispatcher()
    from handlers.seller import seller_router
    dp_seller.include_router(seller_router)
    
    logging.info("Initializing database...")
    await init_db()
    
    logging.info("Starting Web Admin Panel...")
    from uvicorn import Config, Server
    from web_admin import app
    import os
    port = int(os.environ.get("PORT", 8000))
    config = Config(app=app, host="0.0.0.0", port=port, log_level="info")
    server = Server(config)
    
    # Run everything
    logging.info("Starting Dual-Bot ecosystem...")
    await bot_buyer.set_my_commands([BotCommand(command="start", description="دخول المتجر")])
    await bot_seller.set_my_commands([BotCommand(command="start", description="بيع أرقام")])

    await asyncio.gather(
        dp_buyer.start_polling(bot_buyer),
        dp_seller.start_polling(bot_seller),
        auto_approve_task(bot_seller),
        server.serve()
    )

if __name__ == "__main__":
    asyncio.run(main())
