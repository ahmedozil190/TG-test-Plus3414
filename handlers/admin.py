import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database.engine import async_session
from database.models import Account, AccountStatus, User, Transaction, TransactionType
from sqlalchemy.future import select
from sqlalchemy import func
from config import ADMIN_IDS
from keyboards.admin import admin_main_keyboard, admin_user_keyboard, admin_back_keyboard
from states.admin_state import AdminState

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
        
    web_url = os.getenv("WEB_URL", "http://127.0.0.1:8000").rstrip("/")
    text = (
        "🚀 **لوحة تحكم الإدارة (Web Panel)**\n\n"
        "لقد وفرنا لك لوحة تحكم رسومية فخمة للتحكم الكامل في المستخدمين، الأرصدة، وسجل العمليات!\n\n"
        f"🔗 **الرابط:** {web_url}/admin\n"
        "👤 **اليوزر:** `admin`\n"
        "🔑 **الباسورد:** `admin123`\n\n"
        "*(تنبيه: ليظهر رابط Railway هنا، قم بإضافة المتغير WEB_URL في منصة ريلواي)*"
    )
    await message.answer(text, parse_mode="Markdown")

@router.callback_query(F.data == "admin_main")
async def cq_admin_main(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.clear()
    await call.message.edit_text("👨‍💻 **لوحة تحكم الإدارة الرئيسية:**\nاختر من القائمة أدناه:", reply_markup=admin_main_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "admin_stats")
async def cq_admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    
    async with async_session() as session:
        users_count = (await session.execute(select(func.count(User.id)))).scalar()
        total_balance = (await session.execute(select(func.sum(User.balance)))).scalar() or 0.0
        
        avail_count = (await session.execute(select(func.count(Account.id)).where(Account.status == AccountStatus.AVAILABLE))).scalar()
        sold_count = (await session.execute(select(func.count(Account.id)).where(Account.status == AccountStatus.SOLD))).scalar()
        
    text = (
        "📊 **الإحصائيات العامة للمتجر:**\n\n"
        f"👥 **إجمالي المستخدمين:** {users_count}\n"
        f"💰 **إجمالي الأرصدة المودعة:** ${total_balance:.2f}\n\n"
        f"📱 **الأرقام المتاحة للبيع:** {avail_count}\n"
        f"✅ **الأرقام المباعة:** {sold_count}"
    )
    await call.message.edit_text(text, reply_markup=admin_back_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "admin_users")
async def cq_admin_users(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("ارسل آي دي (ID) المستخدم للبحث عنه:", reply_markup=admin_back_keyboard())
    await state.set_state(AdminState.waiting_for_user_id)

@router.message(AdminState.waiting_for_user_id)
async def process_user_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("يرجى إرسال ID صحيح (أرقام فقط).")
        return
        
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        
    if not user:
        await message.answer("المستخدم غير موجود في قاعدة البيانات.", reply_markup=admin_back_keyboard())
        return
        
    text = (
        f"👤 **بيانات المستخدم:**\n"
        f"**ID:** `{user.id}`\n"
        f"**الرصيد الكلي:** `${user.balance:.2f}`\n"
        f"**تاريخ الانضمام:** {user.join_date.strftime('%Y-%m-%d')}"
    )
    await message.answer(text, reply_markup=admin_user_keyboard(user.id), parse_mode="Markdown")
    await state.clear()

# Add / Sub Balance callbacks
@router.callback_query(F.data.startswith("usr_add_"))
async def cq_add_balance(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    user_id = call.data.split("_")[2]
    await state.update_data(target_user_id=int(user_id))
    await call.message.edit_text(f"أرسل المبلغ الذي تود إضافته للمستخدم {user_id}:", reply_markup=admin_back_keyboard())
    await state.set_state(AdminState.waiting_for_add_balance)

@router.message(AdminState.waiting_for_add_balance)
async def process_add_balance(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    target_id = data.get("target_user_id")
    
    try:
        amount = float(message.text.strip())
        if amount <= 0: raise ValueError
    except ValueError:
        await message.answer("الرجاء إدخال مبلغ صحيح أكبر من 0.")
        return
        
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == target_id))).scalar_one_or_none()
        if user:
            user.balance += amount
            txn = Transaction(user_id=target_id, type=TransactionType.DEPOSIT, amount=amount)
            session.add(txn)
            await session.commit()
            await message.answer(f"✅ تم إضافة ${amount:.2f} لرصيد المستخدم بنجاح.\nالرصيد الجديد: ${user.balance:.2f}", reply_markup=admin_back_keyboard())
        else:
            await message.answer("حدث خطأ، المستخدم غير موجود.")
    await state.clear()
    
@router.callback_query(F.data.startswith("usr_sub_"))
async def cq_sub_balance(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    user_id = call.data.split("_")[2]
    await state.update_data(target_user_id=int(user_id))
    await call.message.edit_text(f"أرسل المبلغ الذي تود خصمه من المستخدم {user_id}:", reply_markup=admin_back_keyboard())
    await state.set_state(AdminState.waiting_for_sub_balance)

@router.message(AdminState.waiting_for_sub_balance)
async def process_sub_balance(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    target_id = data.get("target_user_id")
    
    try:
        amount = float(message.text.strip())
        if amount <= 0: raise ValueError
    except ValueError:
        await message.answer("الرجاء إدخال مبلغ صحيح أكبر من 0.")
        return
        
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == target_id))).scalar_one_or_none()
        if user:
            if user.balance < amount:
                await message.answer("المبلغ المدخل أكبر من رصيد المستخدم!", reply_markup=admin_back_keyboard())
                return
            user.balance -= amount
            await session.commit()
            await message.answer(f"✅ تم خصم ${amount:.2f} من رصيد المستخدم بنجاح.\nالرصيد المتبقي: ${user.balance:.2f}", reply_markup=admin_back_keyboard())
        else:
            await message.answer("حدث خطأ، المستخدم غير موجود.")
    await state.clear()


@router.callback_query(F.data == "admin_broadcast")
async def cq_broadcast(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("الرجاء إرسال الرسالة التي تود تعميمها على جميع المستخدمين (نص، صورة، فيديو... يدعم كل شيء):", reply_markup=admin_back_keyboard())
    await state.set_state(AdminState.waiting_for_broadcast)

@router.message(AdminState.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    
    await message.answer("جاري الإرسال... 🚀")
    
    async with async_session() as session:
        users = (await session.execute(select(User.id))).scalars().all()
        
    success = 0
    fail = 0
    for uid in users:
        try:
            await message.copy_to(chat_id=uid)
            success += 1
        except Exception:
            fail += 1
            
    await message.answer(f"✅ تمت الإذاعة بنجاح!\n\nاستلمها: {success}\nفشل الإرسال لـ: {fail} (قد يكونوا أوقفوا البوت)", reply_markup=admin_main_keyboard())
    await state.clear()
    
@router.callback_query(F.data == "admin_stock")
async def cq_admin_stock(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    await call.answer("إدارة تسعير ومخزون الأرقام سيتم برمجتها قريباً كجزء من اللوحة!", show_alert=True)
