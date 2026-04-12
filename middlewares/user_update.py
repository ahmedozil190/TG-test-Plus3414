from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TGUser
from database.models import User
from database.engine import async_session
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

class UserUpdateMiddleware(BaseMiddleware):
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
                        # Auto-create if not exists (helpful for background sync)
                        user = User(
                            id=user_id, 
                            balance=0.0, 
                            full_name=full_name, 
                            username=username
                        )
                        session.add(user)
                        logger.info(f"Middleware: Created new user {user_id}")
                    else:
                        # Update if changed
                        changed = False
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
