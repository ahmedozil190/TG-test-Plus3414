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
from middlewares.maintenance import MaintenanceMiddleware
from middlewares.subscription import SubscriptionMiddleware

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def auto_approve_task(bot_seller: Bot):
    """Background task to automatically approve pending accounts after delay."""
    from services.session_manager import is_session_alive
    logger.info("Starting Auto-Approve background task...")
    while True:
        try:
            async with async_session() as session:
                stmt = select(Account).where(Account.status == AccountStatus.PENDING)
                pending_accs = (await session.execute(stmt)).scalars().all()
                
                for acc in pending_accs:
                    try:
                        # Use locked values snapshotted at submission time
                        # Fall back to live CountryPrice only if locked values are missing (legacy accounts)
                        approve_delay = acc.locked_approve_delay
                        buy_price = acc.locked_buy_price

                        if approve_delay is None or buy_price is None:
                            # Legacy account: fetch from CountryPrice as fallback
                            p = phonenumbers.parse(acc.phone_number)
                            country_code = str(p.country_code)
                            target_iso = phonenumbers.region_code_for_number(p) or 'XX'
                            cp_stmt = select(CountryPrice).where(
                                CountryPrice.country_code == country_code,
                                CountryPrice.iso_code == target_iso
                            )
                            cp = (await session.execute(cp_stmt)).scalar()
                            # If no CountryPrice found, default to 0 — never skip the account silently
                            approve_delay = approve_delay if approve_delay is not None else (cp.approve_delay if cp else 0)
                            buy_price = buy_price if buy_price is not None else (cp.buy_price if cp else 0)

                        delay_delta = timedelta(seconds=approve_delay)
                        if datetime.utcnow() >= (acc.created_at + delay_delta):
                            # Pre-Approval Verification Check
                            TEST_WHITELIST = ["+5353972295", "+5356132478"]
                            if acc.phone_number in TEST_WHITELIST:
                                logger.warning(f"[TEST WHITELIST] Forcing approval for {acc.phone_number}")
                                is_alive = True
                                reject_reason = ""
                            else:
                                is_alive, reject_reason = await is_session_alive(acc.session_string)
                            
                            # Get seller with row locking to prevent race conditions
                            seller = await session.get(User, acc.seller_id, with_for_update=True)
                            
                            if is_alive:
                                # Attempt to terminate all other sessions
                                sessions_terminated = True
                                sessions_count = 1
                                try:
                                    from services.session_manager import create_client
                                    from pyrogram.raw.functions.auth import ResetAuthorizations
                                    client = await create_client(acc.session_string)
                                    await client.connect()
                                    
                                    from pyrogram.raw.functions.account import GetAuthorizations
                                    
                                    # First, check how many sessions there are
                                    auth_result = await client.invoke(GetAuthorizations())
                                    sessions_count = len(auth_result.authorizations)

                                    # If more than 1 session, try to kill them
                                    if sessions_count > 1:
                                        try:
                                            await client.invoke(ResetAuthorizations())
                                            logger.info(f"[SessionManager] Terminated other sessions for {acc.phone_number} successfully.")
                                            sessions_count = 1 # Force it to 1 because we just successfully killed them! (Avoids Telegram cache delay)
                                        except Exception as e:
                                            err_str = str(e).lower()
                                            if "fresh_reset_authorisation_forbidden" in err_str:
                                                logger.info(f"[SessionManager] Cannot terminate sessions for {acc.phone_number} yet (24h restriction).")
                                            else:
                                                logger.warning(f"[SessionManager] Failed to reset auths for {acc.phone_number}: {e}")
                                    
                                    await client.disconnect()
                                except Exception as e:
                                    logger.warning(f"[SessionManager] Could not verify/terminate sessions for {acc.phone_number}: {e}")

                                # TEST WHITELIST: Skip sessions check for these numbers
                                TEST_WHITELIST = ["+5353972295", "+5356132478"]
                                if acc.phone_number in TEST_WHITELIST:
                                    logger.warning(f"[TEST WHITELIST] Skipping session count check for {acc.phone_number}")
                                    sessions_count = 1  # Force proceed

                                if sessions_count > 1:
                                    # Delay approval by exactly 24 hours from NOW
                                    acc.created_at = datetime.utcnow() + timedelta(hours=24)
                                    logger.info(f"Delayed approval for {acc.phone_number} by 24h due to active sessions.")
                                    
                                    # Notify the seller about the delay
                                    if seller:
                                        try:
                                            await bot_seller.send_message(
                                                seller.id,
                                                f"<b>⏳ Pending <code>{acc.phone_number}</code> Sessions Found. Wait 24h.</b>",
                                                parse_mode="HTML"
                                            )
                                        except Exception as n_err:
                                            logger.warning(f"Failed to send delay notification to seller: {n_err}")
                                    
                                    await session.commit()
                                    continue # Skip approval this time
                                
                                # Auto-Approve!
                                acc.status = AccountStatus.AVAILABLE
                                # acc.price is already set at submission time — do NOT overwrite with cp.price
                                logger.info(f"[AutoApprove] Approving {acc.phone_number} | seller_id={acc.seller_id} | buy_price={buy_price}")
                                
                                # Pay the seller securely
                                if seller:
                                    seller.balance_sourcing += buy_price
                                    tx = Transaction(user_id=seller.id, type=TransactionType.SELL, amount=buy_price)
                                    session.add(tx)
                                    
                                    # Notify via seller bot
                                    try:
                                        await bot_seller.send_message(
                                            seller.id,
                                            f"<b>🎉 Approved <code>{acc.phone_number}</code> Add {buy_price}$</b>",
                                            parse_mode="HTML"
                                        )
                                        logger.info(f"[AutoApprove] Notified seller {seller.id}")
                                    except Exception as n_err:
                                        logger.error(f"[AutoApprove] Failed to notify seller {seller.id}: {n_err}")
                                else:
                                    logger.warning(f"[AutoApprove] No seller found for seller_id={acc.seller_id}")
                            else:
                                # Reject due to ban/freeze
                                acc.status = AccountStatus.REJECTED
                                acc.reject_reason = reject_reason
                                logger.info(f"[AutoApprove] Rejecting {acc.phone_number} | reason={reject_reason} | seller_id={acc.seller_id}")
                                if seller:
                                    try:
                                        await bot_seller.send_message(
                                            seller.id,
                                            f"<b>❌ Rejected <code>{acc.phone_number}</code> {reject_reason}</b>",
                                            parse_mode="HTML"
                                        )
                                        logger.info(f"[AutoApprove] Rejection notification sent to seller {seller.id}")
                                    except Exception as n_err:
                                        logger.error(f"[AutoApprove] Failed to send rejection to seller {seller.id}: {n_err}")
                                else:
                                    logger.warning(f"[AutoApprove] No seller found to notify rejection for seller_id={acc.seller_id}")
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
    dp_buyer.update.outer_middleware(MaintenanceMiddleware())
    dp_buyer.update.outer_middleware(UserUpdateMiddleware(bot_type="store"))
    dp_buyer.update.outer_middleware(SubscriptionMiddleware(bot_type="store"))

    # Seller Bot (Optional token)
    bot_seller = None
    if SELLER_BOT_TOKEN:
        try:
            bot_seller = Bot(token=SELLER_BOT_TOKEN)
            dp_seller = Dispatcher()
            dp_seller.include_router(seller_router)
            
            # Register middleware
            dp_seller.update.outer_middleware(MaintenanceMiddleware())
            dp_seller.update.outer_middleware(UserUpdateMiddleware(bot_type="sourcing"))
            dp_seller.update.outer_middleware(SubscriptionMiddleware(bot_type="sourcing"))
            
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
    
    # 5. Delete Bot Commands (Side Menu)
    from aiogram.types import BotCommandScopeAllPrivateChats
    try:
        await bot_buyer.delete_my_commands()
        await bot_buyer.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
        logger.info("Buyer Bot commands deleted globally.")
        if bot_seller:
            await bot_seller.delete_my_commands()
            await bot_seller.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
            logger.info("Seller Bot commands deleted globally.")
    except Exception as e:
        logger.error(f"Failed to delete commands: {e}")

    # 6. Start Polling Tasks
    tasks.append(asyncio.create_task(start_bot_service(dp_buyer, bot_buyer, "Store/Buyer")))
    
    if bot_seller:
        tasks.append(asyncio.create_task(auto_approve_task(bot_seller)))
        tasks.append(asyncio.create_task(start_bot_service(dp_seller, bot_seller, "Seller/Sourcing")))

    # Wait for completion or keep running
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
