from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from database.engine import async_session
from database.models import User
from sqlalchemy.future import select

router = Router()

@router.message(Command("ping"))
async def seller_ping(message: Message):
    await message.answer("Sourcing Bot is Ready! 🚀")

@router.message(Command("start"))
async def seller_start_cmd(message: Message):
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == message.from_user.id))).scalar_one_or_none()
        if not user:
            user = User(id=message.from_user.id)
            session.add(user)
            await session.commit()
        
    welcome_text = (
        "- Welcome to the account reception bot .\n\n"
        "-  To start, send the desired virtual account number or send /help for assistance."
    )
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Add Number for Sale", callback_data="seller_add_account")],
        [InlineKeyboardButton(text="📊 My Balance & Stats", callback_data="seller_my_stats")],
        [InlineKeyboardButton(text="📜 Rules & Prices", callback_data="seller_rules")],
        [InlineKeyboardButton(text="💬 Support", url="https://t.me/your_support_link")]
    ])
    
    await message.answer(welcome_text, reply_markup=markup)

@router.message(Command("coin"))
async def seller_coin_cmd(message: Message):
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == message.from_user.id))).scalar_one_or_none()
        balance = user.balance if user else 0.0
    await message.answer(f"💰 Your Current Balance: **${balance:.2f}**", parse_mode="Markdown")

@router.message(Command("cap"))
async def seller_cap_cmd(message: Message, state: FSMContext):
    from .sell_logic import seller_add_start
    # We simulate the callback to start the sell flow
    await seller_add_start(message, state)

@router.message(Command("cancel"))
async def seller_cancel_cmd(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Current operation cancelled.")

@router.message(Command("language"))
async def seller_language_cmd(message: Message):
    await message.answer("🌐 Language selection is coming soon!")

@router.message(Command("help"))
async def seller_help_cmd(message: Message):
    await message.answer("❓ Need help? Please contact our support team: @your_support_link")

@router.callback_query(F.data == "seller_back_main")
async def seller_back_main(call: CallbackQuery):
    # Re-run the start logic
    await seller_start_cmd(call.message)
