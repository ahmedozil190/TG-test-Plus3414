from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from database.engine import async_session
from database.models import AppSetting
from sqlalchemy import select
from config import ADMIN_IDS
import logging

logger = logging.getLogger(__name__)

class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Check if user is admin
        user = data.get("event_from_user")
        if user and user.id in ADMIN_IDS:
            return await handler(event, data)

        try:
            async with async_session() as session:
                stmt = select(AppSetting).where(AppSetting.key == "maintenance_mode")
                result = await session.execute(stmt)
                setting = result.scalar_one_or_none()
                
                if setting and setting.value.lower() == "true":
                    # Determine if we should block this update
                    from aiogram.types import Update
                    
                    target = None
                    if isinstance(event, Message):
                        target = event
                    elif isinstance(event, CallbackQuery):
                        target = event
                    elif isinstance(event, Update):
                        if event.message:
                            target = event.message
                        elif event.callback_query:
                            target = event.callback_query

                    if target:
                        if isinstance(target, Message):
                            await target.answer("⚠️ البوت في وضع الصيانة حالياً. يرجى المحاولة لاحقاً.\n\n⚠️ The bot is currently in maintenance mode. Please try again later.")
                        elif isinstance(target, CallbackQuery):
                            await target.answer("البوت في وضع الصيانة - Maintenance Mode", show_alert=True)
                        return
        except Exception as e:
            logger.error(f"MaintenanceMiddleware Error: {e}")

        return await handler(event, data)
