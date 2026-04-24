from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardRemove, BotCommand, BotCommandScopeChat, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, MenuButtonWebApp
from config import SELLER_URL
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from database.engine import async_session
from database.models import User, CountryPrice
from sqlalchemy.future import select

router = Router()

@router.message(Command("ping"))
async def seller_ping(message: Message):
    await message.answer("Sourcing Bot is Ready! 🚀")

@router.message(F.text.in_({"عربي", "English"}))
async def seller_change_language(message: Message):
    lang_code = "ar" if message.text == "عربي" else "en"
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == message.from_user.id))).scalar_one_or_none()
        if user:
            user.language = lang_code
            await session.commit()
    
    # Just show the start message without any confirmation text
    await seller_start_cmd(message)

@router.message(Command("start"))
async def seller_start_cmd(message: Message, bot: Bot = None):
    # Force refresh commands if bot is provided (during manual /start)
    if bot:
        try:
            await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=message.from_user.id))
            # Set the "Open Panel" menu button
            await bot.set_chat_menu_button(
                chat_id=message.from_user.id,
                menu_button=MenuButtonWebApp(text="Open Panel", web_app=WebAppInfo(url=SELLER_URL))
            )
        except:
            pass

    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == message.from_user.id))).scalar_one_or_none()
        if not user:
            user = User(id=message.from_user.id, language="en", is_active_sourcing=True)
            session.add(user)
            await session.commit()
        
        if user.is_banned_sourcing:
            await message.answer("🚫 عذراً، لقد تم حظرك من استخدام بوت التوريد.")
            return
        
    lang = user.language
    if lang == "ar":
        welcome_text = (
            "- مرحبًا بك في لوحة استقبال الحسابات الاحترافية 🎊 .\n\n"
            "- اضغط على الزر أدناه لبدء بيع حساباتك ومتابعة أرباحك بشكل أسرع وأكثر سلاسة."
        )
        btn_panel = "🚀 فتح لوحة الموردين"
        btn_balance = "💰 عرض رصيدي"
        btn_prices = "📊 قائمة الأسعار"
        btn_support = "🆘 الدعم الفني"
    else:
        welcome_text = (
            "- Welcome to the Professional Sourcing Panel 🎊 .\n\n"
            "- Click the button below to start selling your accounts and track your earnings faster and smoother."
        )
        btn_panel = "🚀 Open Sourcing Panel"
        btn_balance = "💰 View My Balance"
        btn_prices = "📊 Price List"
        btn_support = "🆘 Support"
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_panel, web_app=WebAppInfo(url=SELLER_URL))]
    ])
    
    await message.answer(welcome_text, reply_markup=markup)

