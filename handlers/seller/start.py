from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardRemove, BotCommand, BotCommandScopeChat, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from database.engine import async_session
from database.models import User
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
        user_commands = [
            BotCommand(command="start", description="/start"),
            BotCommand(command="coin", description="/coin"),
            BotCommand(command="cancel", description="/cancel"),
            BotCommand(command="language", description="/language"),
            BotCommand(command="cap", description="/cap")
        ]
        try:
            await bot.set_my_commands(user_commands, scope=BotCommandScopeChat(chat_id=message.from_user.id))
        except:
            pass

    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == message.from_user.id))).scalar_one_or_none()
        if not user:
            user = User(id=message.from_user.id, language="en")
            session.add(user)
            await session.commit()
        
    lang = user.language
    if lang == "ar":
        welcome_text = (
            "- مرحبًا بك في روبوت استقبال الحسابات 🎊 .\n\n"
            "- 👉 للبدء ، أرسل رقم الحساب الافتراضي المطلوب أو أرسل /help للحصول على المساعدة ."
        )
    else:
        welcome_text = (
            "- Welcome to the account reception bot .\n\n"
            "-  To start, send the desired virtual account number or send /help for assistance."
        )
    
    await message.answer(welcome_text, reply_markup=ReplyKeyboardRemove())

@router.message(Command("coin"))
async def seller_coin_cmd(message: Message):
    try:
        from datetime import datetime, timedelta, timezone
        async with async_session() as session:
            user = (await session.execute(select(User).where(User.id == message.from_user.id))).scalar_one_or_none()
            if not user:
                # Create user if missing
                user = User(id=message.from_user.id, language="ar")
                session.add(user)
                await session.commit()
                balance = 0.0
                lang = "ar"
            else:
                balance = user.balance
                lang = user.language
        
        now_utc = datetime.now(timezone.utc)
        now_egypt = now_utc + timedelta(hours=2)
        now = now_egypt.strftime("%Y/%m/%d - %I:%M:%S")
        
        balance_display = int(balance) if balance == int(balance) else balance
        coin_text = (
            f"💵 Your user account in the robot:\n\n"
            f"👤ID: <code>{message.from_user.id}</code>\n"
            f"💰 Your balance: {balance_display}$\n\n"
            f"⏰ This post was taken in {now}"
        )
        
        withdraw_text = "☑️ سحب الأموال ✅" if lang == "ar" else "☑️ Withdraw funds ✅"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=withdraw_text, callback_data="seller_withdraw")]
        ])
        
        await message.reply(coin_text, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"⚠️ Error: {str(e)}")

@router.message(Command("cap"))
async def seller_cap_cmd(message: Message):
    import phonenumbers
    from phonenumbers import region_code_for_country_code
    
    def get_flag(iso_code):
        if not iso_code: return "🌐"
        if iso_code == "ZZ": return "🌐"
        return "".join(chr(127397 + ord(c)) for c in iso_code.upper())

    async with async_session() as session:
        result = await session.execute(
            select(CountryPrice).order_by(CountryPrice.id.asc())
        )
        countries = result.scalars().all()
    
    if not countries:
        await message.answer("<b>📊 Buying Prices List</b>\n\n- The list is currently empty.", parse_mode="HTML")
        return

    text_lines = ["<b>📊 Buying Prices List:</b>\n"]
    for i, c in enumerate(countries, 1):
        try:
            iso = region_code_for_country_code(int(c.country_code))
            flag = get_flag(iso)
        except:
            iso = "??"
            flag = "🌐"
            
        # Format: 1- 🇻🇺 +678 -VU: $0.55
        line = f"{i}- {flag} +{c.country_code} -{iso}: ${c.buy_price:.2f}"
        text_lines.append(line)
    
    final_text = "\n".join(text_lines)
    if len(final_text) > 4000:
        for i in range(0, len(text_lines), 50):
            chunk = "\n".join(text_lines[i:i+50])
            await message.answer(chunk, parse_mode="HTML")
    else:
        await message.answer(final_text, parse_mode="HTML")

@router.message(Command("cancel"))
async def seller_cancel_cmd(message: Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == message.from_user.id))).scalar_one_or_none()
        lang = user.language if user else "en"

    if lang == "ar":
        cancel_text = (
            "❎- تم إلغاء العملية! للمتابعة،\n\n"
            " أرسل رقم الحساب الافتراضي المطلوب أو أرسل /help للحصول على المساعدة."
        )
    else:
        cancel_text = (
            "❎ The process has been canceled! To continue,\n\n"
            "send the desired virtual account number or send /help for assistance."
        )
    await message.answer(cancel_text)

@router.message(Command("language"))
async def seller_language_cmd(message: Message):
    lang_text = (
        "- الرجاء اختيار اللغة المفضلة لديك .\n\n"
        "- Please choose your preferred language ."
    )
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="عربي"), KeyboardButton(text="English")]
        ],
        resize_keyboard=True
    )
    await message.answer(lang_text, reply_markup=markup)

@router.message(Command("help"))
async def seller_help_cmd(message: Message):
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == message.from_user.id))).scalar_one_or_none()
        lang = user.language if user else "en"
        
    if lang == "ar":
        help_text = (
            "✅-الشرح المطلوب في قناة الروبوت موجود على العنوان التالي:\n"
            "- https://t.me/+WvuURnelU2kzM2Rk\n"
            "♻️- في حال عدم وجود إجابة سؤالك في القناة يمكنك التواصل مع : @FE4EE\n\n"
            "/cancel"
        )
    else:
        help_text = (
            "✅-The explanation required in the robot channel is at the following address:\n"
            "- https://t.me/+WvuURnelU2kzM2Rk\n"
            "♻️ If the answer to your question is not in the channel, you can contact : @FE4EE\n\n"
            "/cancel"
        )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="VIEW CHANNEL", url="https://t.me/+WvuURnelU2kzM2Rk")]
    ])
    await message.answer(help_text, reply_markup=markup, parse_mode="HTML")

@router.callback_query(F.data == "seller_back_main")
async def seller_back_main(call: CallbackQuery):
    # Re-run the start logic
    await seller_start_cmd(call.message)
