from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.engine import async_session
from database.models import SubscriptionChannel
from sqlalchemy import select
from config import ADMIN_IDS
import logging

logger = logging.getLogger(__name__)

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            # Only check for Messages and CallbackQueries
            if not isinstance(event, (Message, CallbackQuery)):
                return await handler(event, data)

            user_id = event.from_user.id
            bot: Bot = data.get("bot")
            
            # Admins bypass subscription check
            if user_id in ADMIN_IDS:
                return await handler(event, data)

            async with async_session() as session:
                result = await session.execute(select(SubscriptionChannel))
                channels = result.scalars().all()

            if not channels:
                return await handler(event, data)

            not_subscribed = []
            for channel in channels:
                try:
                    # Use username (which should be @channel or channel_id)
                    chat_id = channel.username
                    member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                    if member.status in ["left", "kicked"]:
                        not_subscribed.append(channel)
                except Exception as e:
                    logger.error(f"Error checking sub for {chat_id}: {e}")
                    # If bot can't check (e.g. not admin in channel), skip it or assume not subscribed?
                    # Usually better to skip if bot is not admin to avoid blocking everyone if misconfigured.
                    continue

            if not_subscribed:
                # User is not subscribed to one or more channels
                buttons = []
                for ch in not_subscribed:
                    # Ensure link starts with http
                    link = ch.link if ch.link.startswith("http") else f"https://t.me/{ch.username.replace('@','')}"
                    buttons.append([InlineKeyboardButton(text=f"Join Channel", url=link)])
                
                kb = InlineKeyboardMarkup(inline_keyboard=buttons)
                
                msg = (
                    "🔒 <b>Subscription Required</b>\n\n"
                    "Sorry, you must join our channel first to use the bot:\n\n"
                    "✅ <b>After joining, send /start</b>"
                )
                
                if isinstance(event, Message):
                    await event.answer(msg, reply_markup=kb, parse_mode="HTML")
                elif isinstance(event, CallbackQuery):
                    # For callback queries, we might want to send a new message or alert
                    await event.message.answer(msg, reply_markup=kb, parse_mode="HTML")
                    await event.answer()
                
                return # Block further processing

            return await handler(event, data)
        except Exception as e:
            logger.error(f"SubscriptionMiddleware Error: {e}")
            return await handler(event, data)
