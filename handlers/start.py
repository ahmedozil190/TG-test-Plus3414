from aiogram import Router, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, BotCommand, BotCommandScopeChat, WebAppInfo, MenuButtonWebApp, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.future import select
from sqlalchemy import func
from database.models import User
from database.engine import async_session
from keyboards.client import main_keyboard
from config import STORE_URL

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot = None):
    # Force refresh commands and menu button if bot is provided
    if bot:
        try:
            await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=message.from_user.id))
            # Set the "Open Panel" menu button (The blue button in the bottom left)
            await bot.set_chat_menu_button(
                chat_id=message.from_user.id,
                menu_button=MenuButtonWebApp(text="Open", web_app=WebAppInfo(url=STORE_URL))
            )
        except Exception as e:
            pass

    user_id = message.from_user.id
    
    # Extract referral ID
    args = message.text.split()
    referral_id = None
    if len(args) > 1:
        start_param = args[1]
        if start_param.startswith("REF"):
            try:
                referral_id = int(start_param.replace("REF", ""))
            except ValueError:
                pass
        else:
            try:
                referral_id = int(start_param)
            except ValueError:
                pass
    
    # Referral and user creation is now handled by UserUpdateMiddleware
    await message.answer(
        "Welcome to the Store! 🛒\nClick the button below to open.",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(lambda c: c.data == "my_referral")
async def cq_my_referral(call: CallbackQuery, bot: Bot):
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == call.from_user.id))).scalar_one_or_none()
        if not user:
            return
            
        refs_count = (await session.execute(select(func.count(User.id)).where(User.referred_by == user.id))).scalar() or 0
        
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=REF{user.id}"
    
    text = (
        "Share your referral link with your friends or channels and earn rewards:\n"
        "• <b>$0.005</b> for each person who joins.\n"
        "• <b>1% commission</b> on all their deposits!\n\n"
        f"🔗 <b>Your Link:</b>\n<code>{ref_link}</code>\n\n"
        f"👥 <b>Total Referrals:</b> {refs_count}\n"
        f"💰 <b>Total Earnings:</b> ${user.referral_earnings or 0.0:.3f}"
    )
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Back 🔙", callback_data="back_main")]
    ])
    
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=markup)

@router.callback_query(lambda c: c.data == "back_main")
async def cq_back_main(call: CallbackQuery):
    await call.message.edit_text(
        "Welcome to the Store! 🛒\nClick the button below to open.",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )
