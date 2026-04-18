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
        user_commands = [
            BotCommand(command="start", description="/start"),
            BotCommand(command="coin", description="/coin"),
            BotCommand(command="cancel", description="/cancel"),
            BotCommand(command="language", description="/language"),
            BotCommand(command="cap", description="/cap")
        ]
        try:
            await bot.set_my_commands(user_commands, scope=BotCommandScopeChat(chat_id=message.from_user.id))
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
        [InlineKeyboardButton(text=btn_panel, web_app=WebAppInfo(url=SELLER_URL))],
        [
            InlineKeyboardButton(text=btn_balance, callback_data="seller_coin_info"),
            InlineKeyboardButton(text=btn_prices, callback_data="seller_price_list")
        ],
        [InlineKeyboardButton(text=btn_support, url="https://t.me/FE4EE")]
    ])
    
    await message.answer(welcome_text, reply_markup=markup)

@router.message(Command("coin"))
async def seller_coin_cmd(message: Message):
    try:
        from datetime import datetime, timedelta, timezone
        async with async_session() as session:
            user = (await session.execute(select(User).where(User.id == message.from_user.id))).scalar_one_or_none()
            if not user:
                # Create user if missing
                user = User(id=message.from_user.id, language="ar", is_active_sourcing=True)
                session.add(user)
                await session.commit()
                balance = 0.0
                lang = "ar"
            else:
                if user.is_banned_sourcing:
                    await message.answer("🚫 عذراً، أنت محظور.")
                    return
                balance = user.balance_sourcing
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
    try:
        import phonenumbers
        from phonenumbers import region_code_for_country_code
        
        def get_flag(iso_code):
            if not iso_code: return "🌐"
            if iso_code == "ZZ": return "🌐"
            return "".join(chr(127397 + ord(c)) for c in iso_code.upper())

        async with async_session() as session:
            result = await session.execute(
                select(CountryPrice)
                .where(CountryPrice.buy_price > 0)
                .order_by(CountryPrice.id.asc())
            )
            countries = result.scalars().all()
        
        if not countries:
            await message.answer("<b>📊 Buying Prices List</b>\n\n- The list is currently empty.", parse_mode="HTML")
            return

        text_lines = ["<blockquote expandable>"] # Start expandable quote
        for i, c in enumerate(countries, 1):
            try:
                iso = region_code_for_country_code(int(c.country_code))
                flag = get_flag(iso)
            except:
                iso = "??"
                flag = "🌐"
                
            # Format: 1-🇻🇺 +678 -VU: 0.55$ (Bold for width, no extra spaces)
            line = f"{i}-{flag} +{c.country_code} -{iso}: {c.buy_price:.2f}$"
            text_lines.append(line)
        
        text_lines.append("</blockquote>") # End expandable quote
        
        final_text = "\n".join(text_lines)
        if len(final_text) > 4000:
            for i in range(0, len(text_lines), 50):
                chunk = "\n".join(text_lines[i:i+50])
                if not chunk.startswith("<blockquote"): chunk = "<blockquote expandable>\n" + chunk
                if not chunk.endswith("</blockquote>"): chunk = chunk + "\n</blockquote>"
                await message.answer(chunk, parse_mode="HTML")
        else:
            await message.answer(final_text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"⚠️ Error in /cap: {str(e)}")

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
    await message.answer(help_text, parse_mode="HTML")

@router.callback_query(F.data == "seller_back_main")
async def seller_back_main(call: CallbackQuery):
    # Re-run the start logic
    await seller_start_cmd(call.message)

@router.callback_query(F.data == "seller_coin_info")
async def cq_seller_coin(call: CallbackQuery):
    await seller_coin_cmd(call.message)
    await call.answer()

@router.callback_query(F.data == "seller_price_list")
async def cq_seller_prices(call: CallbackQuery):
    await seller_cap_cmd(call.message)
    await call.answer()
