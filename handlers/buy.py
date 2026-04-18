import logging
import re
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext
from database.engine import async_session
from database.models import Account, AccountStatus, User, Transaction, TransactionType
from sqlalchemy.future import select
from sqlalchemy import func
from services.session_manager import get_telegram_login_code
from states.buy_state import BuyAccountState
from config import STORE_URL

router = Router()

# Mapping for country data (ISO, Key, Flag)
COUNTRY_DATA = {
    "Saudi Arabia": {"flag": "🇸🇦", "iso": "SA", "key": "+966"},
    "Pakistan": {"flag": "🇵🇰", "iso": "PK", "key": "+92"},
    "Afghanistan": {"flag": "🇦🇫", "iso": "AF", "key": "+93"},
    "Australia": {"flag": "🇦🇺", "iso": "AU", "key": "+61"},
    "Congo - Brazzaville": {"flag": "🇨🇬", "iso": "CG", "key": "+242"},
    "Cuba": {"flag": "🇨🇺", "iso": "CU", "key": "+53"},
    "Algeria": {"flag": "🇩🇿", "iso": "DZ", "key": "+213"},
    "India": {"flag": "🇮🇳", "iso": "IN", "key": "+91"},
    "Nigeria": {"flag": "🇳🇬", "iso": "NG", "key": "+234"},
    "Kenya": {"flag": "🇰🇪", "iso": "KE", "key": "+254"},
    "Cameroon": {"flag": "🇨🇲", "iso": "CM", "key": "+237"},
    "Bangladesh": {"flag": "🇧🇩", "iso": "BD", "key": "+880"},
    "Oman": {"flag": "🇴🇲", "iso": "OM", "key": "+968"},
    "Sierra Leone": {"flag": "🇸🇱", "iso": "SL", "key": "+232"},
    "Turkey": {"flag": "🇹🇷", "iso": "TR", "key": "+90"},
    "Venezuela": {"flag": "🇻🇪", "iso": "VE", "key": "+58"},
    "Uganda": {"flag": "🇺🇬", "iso": "UG", "key": "+256"},
    "Tunisia": {"flag": "🇹🇳", "iso": "TN", "key": "+216"},
    "Peru": {"flag": "🇵🇪", "iso": "PE", "key": "+51"},
    "Guyana": {"flag": "🇬🇾", "iso": "GY", "key": "+592"},
    "Palestine": {"flag": "🇵🇸", "iso": "PS", "key": "+970"}
}

def get_country_info(country_name):
    return COUNTRY_DATA.get(country_name, {"flag": "🏳️", "iso": "??", "key": ""})

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

@router.callback_query(F.data == "buy_number")
async def cq_buy_number(call: CallbackQuery, state: FSMContext):
    await state.clear()
    
    async with async_session() as session:
        user = await session.get(User, call.from_user.id)
        if user and user.is_banned_store:
            await call.answer("🚫 عذراً، لقد تم حظرك من الشراء في المتجر.", show_alert=True)
            return

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ فتح متجر الأرقام", web_app=WebAppInfo(url=STORE_URL))],
        [InlineKeyboardButton(text="- عودة.", callback_data="back_main")]
    ])
    
    await call.message.edit_text(
        "✨ **مرحباً بك في المتجر الفاخر**\n\n- اضغط على الزر أدناه لاختيار دولتك والشراء بلمسة واحدة بجودة عالية.",
        parse_mode="Markdown",
        reply_markup=markup
    )

@router.callback_query(F.data == "supplier_main")
async def cq_supplier_main(call: CallbackQuery):
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
            country_name, price, count = row
            info = get_country_info(country_name)
            text = f"{country_name} {info['flag']} : {price}$"
            buttons.append(InlineKeyboardButton(text=text, callback_data=f"buy_c_{country_name}"))
            
        # Chunk into 2 columns
        keyboard = list(chunk_list(buttons, 2))
        
        # Navigation buttons
        keyboard.append([InlineKeyboardButton(text="➡", callback_data="next_page_placeholder")])
        keyboard.append([InlineKeyboardButton(text="🔎 AUTO", callback_data="buy_auto_search")])
        keyboard.append([InlineKeyboardButton(text="- Return.", callback_data="buy_number")])
        
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        text = (
            "- Please choose the country from which you want to buy an account ✅.\n\n"
            "- All countries at the bottom have accounts to activate the telegram, "
            "and receive the arrival of the code on any copy, click on the state to buy 🏆."
        )
        
        await call.message.edit_text(text, reply_markup=markup)

@router.callback_query(F.data == "buy_auto_search")
async def cq_auto_search(call: CallbackQuery, state: FSMContext):
    await state.set_state(BuyAccountState.searching_country)
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="- Return.", callback_data="supplier_main")]
    ])
    
    text = (
        "🔎 | Well, you can now send anything that indicates the country...\n\n"
        "- for example, the ISO code PS, the country key +970, or its flag 🇵🇸, "
        "or a complete number for the country as well."
    )
    
    await call.message.edit_text(text, reply_markup=markup)

@router.message(BuyAccountState.searching_country)
async def process_country_search(message: Message, state: FSMContext):
    search_query = message.text.strip().upper()
    flag_match = re.search(r'[\U0001F1E6-\U0001F1FF]{2}', search_query) # Basic flag regex
    
    matched_country = None
    
    # Logic for "most accurate" match
    async with async_session() as session:
        # Get all distinct available countries from DB
        stmt = select(Account.country).where(Account.status == AccountStatus.AVAILABLE).distinct()
        available_countries = (await session.execute(stmt)).scalars().all()
        
        for country in available_countries:
            info = get_country_info(country)
            
            # Match by ISO
            if search_query == info['iso']:
                matched_country = country
                break
            # Match by Key
            if search_query == info['key'] or search_query == info['key'].replace('+', ''):
                matched_country = country
                break
            # Match by Flag
            if flag_match and flag_match.group(0) == info['flag']:
                matched_country = country
                break
            # Match by Name (Case-insensitive)
            if search_query == country.upper():
                matched_country = country
                break
            # Match by Number prefix (if search_query starts with key)
            if info['key'] and (search_query.startswith(info['key']) or search_query.startswith(info['key'].replace('+', ''))):
                matched_country = country
                break

    if matched_country:
        await state.clear()
        # Mock a callback to cq_confirm_buy logic or just show the country confirm
        # Here we jump to the specific country flow
        call_data = f"buy_c_{matched_country}"
        # We can't easily trigger cq_confirm_buy but we can call it or implement the same logic
        await show_country_confirm(message, matched_country)
    else:
        await message.answer("❌ لم يتم العثور على الدولة المطلوبة أو لا توجد أرقام متوفرة لها.")

async def show_country_confirm(message: Message, country: str):
    async with async_session() as session:
        acc_stmt = select(Account).where(
            Account.country == country,
            Account.status == AccountStatus.AVAILABLE
        ).limit(1)
        account = (await session.execute(acc_stmt)).scalar_one_or_none()
        
        if not account:
            await message.answer("عذراً، نفدت الأرقام من هذه الدولة حالياً.")
            return
            
        text = f"هل تريد شراء رقم من {country} بسعر ${account.price:.2f}؟"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="تأكيد الشراء ✅", callback_data=f"buy_c_{country}")],
            [InlineKeyboardButton(text="إلغاء ❌", callback_data="supplier_main")]
        ])
        await message.answer(text, reply_markup=markup)


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
            
        if user.balance_store < account.price:
            await call.answer("عذراً، رصيدك غير كافٍ لشراء هذا الرقم.", show_alert=True)
            return
            
        # Perform buy
        user.balance_store -= account.price
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
        price = account.price
        
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="أرسل الكود 📥", callback_data=f"getcode_{acc_id}")]
    ])
    
    text = (
        f"✅ **تم الشراء بنجاح!**\n\n"
        f"**الرقم:** `{number}`\n"
        f"**الدولة:** {country}\n"
        f"**تم خصم:** ${price:.2f}\n\n"
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
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == call.from_user.id))).scalar_one_or_none()
        balance = user.balance_store if user else 0.0
        
    await call.message.edit_text(
        "- The main list.\n\n"
        f"- Your balance:{int(balance) if balance == 0 else balance}$ .\n"
        f"- Hands of your account:<code>{call.from_user.id}</code> .\n"
        "Official Bot Channel:@MOOO8O .\n"
        "Gover the bot through the buttons below.",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )
