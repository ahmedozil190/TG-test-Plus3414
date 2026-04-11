from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.future import select
from database.models import User
from database.engine import async_session
from keyboards.client import profile_keyboard

router = Router()

async def get_profile_text(user_id: int, full_name: str) -> str:
    async with async_session() as session:
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        
        if not user:
            return "Please start the bot first using /start"
            
        text = (
            f"👤 **الملف الشخصي: {full_name}**\n\n"
            f"**الرقم التعريفي:** `{user.id}`\n"
            f"**الرصيد:** `${user.balance:.2f}`\n"
            f"**تاريخ الانضمام:** `{user.join_date.strftime('%Y-%m-%d')}`"
        )
        return text

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    text = await get_profile_text(message.from_user.id, message.from_user.full_name)
    await message.answer(text, parse_mode="Markdown", reply_markup=profile_keyboard())

@router.callback_query(F.data == "my_profile")
async def cq_profile(call: CallbackQuery):
    text = await get_profile_text(call.from_user.id, call.from_user.full_name)
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=profile_keyboard())

@router.callback_query(F.data == "customer_service")
async def cq_customer_service(call: CallbackQuery):
    text = (
        "- Hello my friend.\n\n"
        "- You are now in communication with customer service, that is, a message you send will be delivered to the administration immediately.\n"
        "- Any problem you faced in the bot\n"
        "They are around the clock.\n\n"
        "Avoid sending abuse if possible.\n"
        "👮‍♂️:Support: @Q_M_5"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="الرجوع 🔙", callback_data="back_main")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=markup)

@router.callback_query(F.data == "call_link")
async def cq_call_link(call: CallbackQuery):
    bot_info = await call.bot.get_me()
    text = (
        "Your invitation link:\n\n"
        f"t.me/{bot_info.username}?start={call.from_user.id}"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="الرجوع 🔙", callback_data="back_main")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=markup)

@router.callback_query(F.data == "deposit")
async def cq_deposit(call: CallbackQuery):
    await call.answer("ميزة الشحن التلقائي ستتوفر قريباً!\nيرجى التواصل مع الإدارة للشحن اليدوي.", show_alert=True)

@router.callback_query(F.data.in_(["payout", "countries_we_buy", "sales_channel", "api_key"]))
async def cq_placeholders(call: CallbackQuery):
    await call.answer("This feature is coming soon! ميزة قادمة قريباً", show_alert=True)
