import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.engine import async_session
from database.models import Account, AccountStatus, User, Transaction, TransactionType
from sqlalchemy.future import select
from sqlalchemy import func
from services.session_manager import get_telegram_login_code

router = Router()

@router.callback_query(F.data == "buy_number")
async def cq_buy_number(call: CallbackQuery):
    async with async_session() as session:
        # Group accounts by country
        stmt = select(Account.country, Account.price, func.count(Account.id).label('cnt')).where(
            Account.status == AccountStatus.AVAILABLE
        ).group_by(Account.country, Account.price)
        
        results = (await session.execute(stmt)).all()
        
        if not results:
            await call.answer("عذراً، لا توجد أرقام متوفرة حالياً.", show_alert=True)
            return
            
        buttons = []
        for row in results:
            country, price, count = row
            text = f"{country} | ${price:.2f} | متوفر: {count}"
            buttons.append([InlineKeyboardButton(text=text, callback_data=f"buy_c_{country}")])
            
        buttons.append([InlineKeyboardButton(text="الرجوع 🔙", callback_data="back_main")])
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await call.message.edit_text("اختر الدولة التي تريد شراء رقم منها:", reply_markup=markup)


@router.callback_query(F.data.startswith("buy_c_"))
async def cq_confirm_buy(call: CallbackQuery):
    country = call.data.split("_")[2]
    
    async with async_session() as session:
        user_stmt = select(User).where(User.id == call.from_user.id)
        user = (await session.execute(user_stmt)).scalar_one_or_none()
        
        if not user:
            await call.answer("يرجى إرسال /start أولاً.", show_alert=True)
            return
            
        acc_stmt = select(Account).where(
            Account.country == country,
            Account.status == AccountStatus.AVAILABLE
        ).limit(1)
        account = (await session.execute(acc_stmt)).scalar_one_or_none()
        
        if not account:
            await call.answer("عذراً، نفدت الأرقام من هذه الدولة حالياً.", show_alert=True)
            return
            
        if user.balance < account.price:
            await call.answer("عذراً، رصيدك غير كافٍ لشراء هذا الرقم.", show_alert=True)
            return
            
        # Perform buy
        user.balance -= account.price
        account.status = AccountStatus.SOLD
        account.buyer_id = user.id
        
        txn = Transaction(
            user_id=user.id,
            type=TransactionType.BUY,
            amount=-account.price
        )
        session.add(txn)
        await session.commit()
        
        number = account.phone_number
        acc_id = account.id
        
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="أرسل الكود 📥", callback_data=f"getcode_{acc_id}")]
    ])
    
    text = (
        f"✅ **تم الشراء بنجاح!**\n\n"
        f"**الرقم:** `{number}`\n"
        f"**الدولة:** {country}\n"
        f"**تم خصم:** ${account.price:.2f}\n\n"
        f"1️⃣ اذهب إلى تطبيق تلجرام الرسمي\n"
        f"2️⃣ أدخل الرقم أعلاه أو انسخه\n"
        f"3️⃣ اضغط على 'أرسل الكود 📥' في الأسفل للحصول على الكود المكون من 5 أرقام."
    )
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=markup)


@router.callback_query(F.data.startswith("getcode_"))
async def cq_get_code(call: CallbackQuery):
    acc_id = int(call.data.split("_")[1])
    await call.answer("جاري جلب الكود، يرجى الانتظار... قد يستغرق الأمر بعض الوقت.", show_alert=False)
    
    async with async_session() as session:
        stmt = select(Account).where(Account.id == acc_id, Account.buyer_id == call.from_user.id)
        account = (await session.execute(stmt)).scalar_one_or_none()
        
        if not account:
            await call.message.answer("حدث خطأ: الحساب غير موجود أو أنك لست المشتري.")
            return
            
        session_str = account.session_string
        
    code = await get_telegram_login_code(session_str)
    
    if code:
        await call.message.answer(f"🔐 **كود تسجيل الدخول:** `{code}`", parse_mode="Markdown")
    else:
        await call.message.answer("⏳ لم يصل الكود بعد أو حدث خطأ. تأكد من أنك طلبت الكود في تطبيق تلجرام، ثم اضغط على الزر مجدداً.", show_alert=True)

@router.callback_query(F.data == "back_main")
async def cq_back_main(call: CallbackQuery):
    from keyboards.client import main_keyboard
    await call.message.edit_text(
        f"Welcome {call.from_user.full_name} to the Exclusive Numbers Store!\n"
        "Here you can buy Telegram numbers to receive codes, or sell your numbers to us.",
        reply_markup=main_keyboard()
    )
