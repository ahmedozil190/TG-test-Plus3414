from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database.engine import async_session
from database.models import User
from sqlalchemy.future import select

router = Router()

@router.message(Command("start"))
async def seller_start_cmd(message: Message):
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == message.from_user.id))).scalar_one_or_none()
        if not user:
            user = User(id=message.from_user.id)
            session.add(user)
            await session.commit()
        
    balance = user.balance
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 إضافة رقم للبيع", callback_data="seller_add_account")],
        [InlineKeyboardButton(text="📊 رصيدي وأرباحي", callback_data="seller_my_stats")],
        [InlineKeyboardButton(text="📜 قوانين وسعر البيع", callback_data="seller_rules")],
        [InlineKeyboardButton(text="💬 الدعم الفني", url="https://t.me/your_support_link")]
    ])
    
    welcome_text = (
        f"👋 **مرحباً بك في بوت التوريد الرسمي!**\n\n"
        f"هنا يمكنك بيع أرقام التلجرام الخاصة بك والحصول على مبالغ مالية فورية تُضاف لرصيدك.\n\n"
        f"👤 **معلوماتك:**\n"
        f"🆔 معرفك: `{message.from_user.id}`\n"
        f"💰 رصيدك الحالي: **${balance:.2f}**\n\n"
        f"استخدم الأزرار أدناه للبدء في جني الأرباح! 🚀"
    )
    
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=markup)

@router.callback_query(F.data == "seller_back_main")
async def seller_back_main(call: F.data):
    # This is a bit tricky since we're using a common handler. 
    # Usually I would use a different callback but let's just re-run the start logic.
    await seller_start_cmd(call.message)
