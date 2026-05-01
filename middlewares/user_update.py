from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TGUser
from database.models import User
from database.engine import async_session
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

class UserUpdateMiddleware(BaseMiddleware):
    def __init__(self, bot_type: str = "store"):
        self.bot_type = bot_type
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # data contains 'event_from_user' which is the TG user object
        tg_user: TGUser = data.get("event_from_user")
        
        if tg_user and not tg_user.is_bot:
            try:
                async with async_session() as session:
                    user_id = tg_user.id
                    full_name = f"{tg_user.first_name or ''} {tg_user.last_name or ''}".strip() or None
                    username = tg_user.username or None
                    
                    stmt = select(User).where(User.id == user_id)
                    result = await session.execute(stmt)
                    user = result.scalar_one_or_none()
                    
                    if not user:
                        # SECURITY: Check if this is a /start command with referral (to avoid race condition with handlers/start.py)
                        is_referral_start = False
                        
                        # In Aiogram 3 outer_middleware on Dispatcher, 'event' is an Update object
                        from aiogram.types import Update, Message
                        msg = None
                        if isinstance(event, Message):
                            msg = event
                        elif isinstance(event, Update) and event.message:
                            msg = event.message
                            
                        if msg and msg.text and msg.text.startswith('/start') and len(msg.text.split()) > 1:
                            is_referral_start = True
                            logger.info(f"Middleware: Detected referral start for {user_id}, skipping auto-creation.")
                        
                        if not is_referral_start:
                            # Auto-create if not exists (helpful for background sync)
                            user = User(
                                id=user_id, 
                                full_name=full_name, 
                                username=username,
                                is_active_store=(self.bot_type == "store"),
                                is_active_sourcing=(self.bot_type == "sourcing")
                            )
                            session.add(user)
                            logger.info(f"Middleware: Created new user {user_id} for {self.bot_type}")
                    else:
                        # Update if changed
                        changed = False
                        
                        # Set active flag if not already set
                        if self.bot_type == "store" and not user.is_active_store:
                            user.is_active_store = True
                            changed = True
                        elif self.bot_type == "sourcing" and not user.is_active_sourcing:
                            user.is_active_sourcing = True
                            changed = True
                        if user.full_name != full_name:
                            user.full_name = full_name
                            changed = True
                        if user.username != username:
                            user.username = username
                            changed = True
                        
                        if changed:
                            logger.info(f"Middleware: Updated info for user {user_id}")
                    
                    await session.commit()
            except Exception as e:
                logger.error(f"Error in UserUpdateMiddleware: {e}")
        
        return await handler(event, data)
