import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.sell_state import SellAccountState
from services.session_manager import request_app_code, submit_app_code
from database.engine import async_session
from database.models import Account, AccountStatus, User, Transaction, TransactionType
from sqlalchemy.future import select

router = Router()

from keyboards.client import sell_menu_keyboard

@router.callback_query(F.data == "sell_number")
async def cq_sell_number(call: CallbackQuery):
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == call.from_user.id))).scalar_one_or_none()
        balance = user.balance if user else 0.0
        
    text = (
        "- Welcome to the account purchase section.\n\n"
        f"- Total balance : {int(balance) if balance == 0 else balance}$\n"
        f"- Hands your account : <a href=\"tg://user?id={call.from_user.id}\">{call.from_user.id}</a> .\n"
        "- Price : @MOOO8O .\n"
        "Gover the bot through the buttons below."
    )
    await call.message.edit_text(text, reply_markup=sell_menu_keyboard(), parse_mode="HTML")

@router.callback_query(F.data.in_(["sell_prices", "pull_balance"]))
async def cq_sell_closed(call: CallbackQuery):
    await call.answer("This section is currently closed", show_alert=True)

@router.callback_query(F.data == "start_sell_fsm") # Placeholder for if user wants to start FSM later
async def cq_start_sell_fsm(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "أدخل رقم التلجرام الذي تود بيعه مع رمز الدولة (مثال: +1234567890):",
        reply_markup=None
    )
    await state.set_state(SellAccountState.waiting_for_phone)

@router.message(SellAccountState.waiting_for_phone)
async def process_sell_phone(message: Message, state: FSMContext):
    phone = message.text.strip().replace(" ", "")
    if not phone.startswith("+"):
        await message.answer("يرجى إدخال الرقم مع رمز الدولة بـ +")
        return
        
    await message.answer("جاري طلب الكود من تلجرام، الرجاء الانتظار...")
    
    try:
        phone_code_hash = await request_app_code(message.from_user.id, phone)
        await state.update_data(phone=phone, phone_code_hash=phone_code_hash)
        await state.set_state(SellAccountState.waiting_for_code)
        await message.answer("تم إرسال الكود إلى تطبيق تلجرام الخاص بهذا الرقم.\nالرجاء إدخال الكود هنا:")
    except Exception as e:
        logging.error(f"Error requesting code: {e}")
        error_msg = str(e)
        if "PHONE_MIGRATE" in error_msg or "SESSION_PASSWORD_NEEDED" in error_msg or "2fa" in error_msg.lower():
            await message.answer("عذراً، لا ندعم الأرقام المحمية بكلمة مرور أو التي تتطلب ترحيل.")
        else:
            await message.answer(f"فشل في طلب الكود، يرجى المحاولة لاحقاً. ({error_msg})")
        await state.clear()

@router.message(SellAccountState.waiting_for_code)
async def process_sell_code(message: Message, state: FSMContext):
    code = message.text.strip()
    data = await state.get_data()
    phone = data['phone']
    phone_code_hash = data['phone_code_hash']
    
    await message.answer("جاري تسجيل الدخول وحفظ الجلسة...")
    
    session_string = await submit_app_code(message.from_user.id, phone, phone_code_hash, code)
    if not session_string:
        await message.answer("الكود خاطئ أو انتهت صلاحيته. تم إلغاء العملية.")
        await state.clear()
        return
        
    price = 5.0 # Fixed price for selling for now
    
    async with async_session() as session:
        # Check if account already exists
        acc_stmt = select(Account).where(Account.phone_number == phone)
        existing_acc = (await session.execute(acc_stmt)).scalar_one_or_none()
        if existing_acc:
            await message.answer("هذا الرقم موجود مسبقاً في المتجر.")
            await state.clear()
            return

        stmt = select(User).where(User.id == message.from_user.id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if not user:
            user = User(id=message.from_user.id, balance=0.0)
            session.add(user)
            
        country = "Unknown" 
        if phone.startswith("+1"): country = "US"
        elif phone.startswith("+20"): country = "EG"
        elif phone.startswith("+44"): country = "UK"
        elif phone.startswith("+966"): country = "SA"
        
        acc = Account(
            phone_number=phone,
            country=country,
            session_string=session_string,
            status=AccountStatus.AVAILABLE,
            price=price,
            seller_id=message.from_user.id
        )
        session.add(acc)
        
        user.balance += price
        
        txn = Transaction(
            user_id=user.id,
            type=TransactionType.SELL,
            amount=price
        )
        session.add(txn)
        
        await session.commit()
    
    await message.answer(f"✅ تمت إضافة الحساب بنجاح!\nتمت إضافة ${price} إلى رصيدك.")
    await state.clear()
