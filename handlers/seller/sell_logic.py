import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import phonenumbers
from phonenumbers import geocoder
from database.engine import async_session
from database.models import Account, AccountStatus, User, Transaction, TransactionType, CountryPrice
from sqlalchemy.future import select
from services.session_manager import request_app_code, submit_app_code

router = Router()

class SellerAddState(StatesGroup):
    waiting_phone = State()
    waiting_code = State()
    waiting_2fa = State()

@router.callback_query(F.data == "seller_add_account")
async def seller_add_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(SellerAddState.waiting_phone)
    await call.message.answer(
        "📝 **الخطوة 1: أدخل رقم الهاتف**\n\n"
        "يرجى إرسال رقم الهاتف الذي تود بيعه (مع رمز الدولة، مثال: +20123...)",
        parse_mode="Markdown"
    )
    await call.answer()

@router.message(SellerAddState.waiting_phone)
async def seller_process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+"):
        phone = "+" + phone
        
    try:
        parsed = phonenumbers.parse(phone)
        if not phonenumbers.is_valid_number(parsed):
            raise Exception("Invalid")
            
        country_code = str(parsed.country_code)
        
        async with async_session() as session:
            cp = (await session.execute(select(CountryPrice).where(CountryPrice.country_code == country_code))).scalar()
            
            if not cp or cp.buy_price <= 0:
                await message.answer("❌ عذراً، نحن لا نشتري أرقاماً من هذه الدولة حالياً.")
                await state.clear()
                return
            
            buy_price = cp.buy_price
            country_name = cp.country_name
            
        await state.update_data(phone=phone, buy_price=buy_price, country=country_name)
        
        # Step 2: Request Code
        await message.answer(f"⏳ جاري طلب كود التحقق لرقم {phone}...\nدولة: {country_name}\nسعر الشراء: **${buy_price}**", parse_mode="Markdown")
        
        code_hash = await request_app_code(message.from_user.id, phone)
        await state.update_data(hash=code_hash)
        
        await state.set_state(SellerAddState.waiting_code)
        await message.answer(
            "📥 **الخطوة 2: أدخل الكود**\n\n"
            "لقد أرسلنا كوداً إلى حساب التلجرام الخاص بهذا الرقم.\n"
            "يرجى إدخال الكود المكون من 5 أرقام هنا:",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await message.answer("❌ رقم هاتف غير صالح. تأكد من كتابة الرقم بشكل صحيح مع رمز الدولة.")

@router.message(SellerAddState.waiting_code)
async def seller_process_code(message: Message, state: FSMContext):
    code = message.text.strip()
    if not code.isdigit() or len(code) != 5:
        await message.answer("❌ الكود يجب أن يكون 5 أرقام فقط.")
        return
        
    data = await state.get_data()
    phone = data['phone']
    code_hash = data['hash']
    
    await message.answer("⏳ جاري التحقق من الكود وسحب الجلسة...")
    
    try:
        # Attempt to login
        # Note: If 2FA is needed, the current submit_app_code might raise an error or return None
        # We should ideally handle 2FA here, but let's keep it simple first
        session_string = await submit_app_code(message.from_user.id, phone, code_hash, code)
        
        if not session_string:
            await message.answer("❌ فشل التحقق. قد يكون الكود انتهت صلاحيته أو أن الحساب محمي بكلمة سر (2FA).")
            # For 2FA, we would ask for password, but for simplicity we stop here or ask to clear 2FA
            return

        # Save to DB as PENDING
        async with async_session() as session:
            new_acc = Account(
                phone_number=phone,
                country=data['country'],
                price=0, # Will be set to sell_price upon approval
                session_string=session_string,
                status=AccountStatus.PENDING,
                seller_id=message.from_user.id
            )
            session.add(new_acc)
            await session.commit()
            
        await message.answer(
            "✅ **تم استلام الرقم بنجاح!**\n\n"
            "طلبك الآن **قيد المراجعة**. سيتم فحص الحساب وإضافة الرصيد إلى حسابك تلقائياً بعد مرور وقت الموافقة المحدد.\n"
            "شكراً لتوريدك لنا! 🌟",
            parse_mode="Markdown"
        )
        await state.clear()
        
    except Exception as e:
        logging.error(f"Seller login error: {e}")
        await message.answer("❌ حدث خطأ غير متوقع أثناء عملية التحقق.")
