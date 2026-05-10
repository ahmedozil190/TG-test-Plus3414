import logging
from aiogram import Router, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, BotCommand, BotCommandScopeChat, WebAppInfo, MenuButtonWebApp, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.future import select
from sqlalchemy import func
from database.models import User
from database.engine import async_session
from keyboards.client import main_keyboard
from config import STORE_URL

logger = logging.getLogger(__name__)
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot = None):
    # Force refresh commands and menu button if bot is provided
    if bot:
        try:
            await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=message.from_user.id))
            # Set the "Open Panel" menu button (The blue button in the bottom left)
            await bot.set_chat_menu_button(
                chat_id=message.from_user.id,
                menu_button=MenuButtonWebApp(text="Open", web_app=WebAppInfo(url=STORE_URL))
            )
        except Exception as e:
            pass

    user_id = message.from_user.id
    
    # Extract referral ID
    args = message.text.split()
    referral_id = None
    if len(args) > 1:
        start_param = args[1]
        if start_param.startswith("REF"):
            try:
                referral_id = int(start_param.replace("REF", ""))
            except ValueError:
                pass
        else:
            try:
                referral_id = int(start_param)
            except ValueError:
                pass
    
    async with async_session() as session:
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user and user.referred_by and not user.referral_bonus_awarded:
            referrer_id = user.referred_by
            async with async_session() as ref_session:
                referrer = (await ref_session.execute(select(User).where(User.id == referrer_id))).scalar_one_or_none()
                if referrer:
                    from database.models import AppSetting, Transaction, TransactionType
                    bonus_obj = (await ref_session.execute(select(AppSetting).where(AppSetting.key == "referral_join_bonus"))).scalar_one_or_none()
                    bonus_val = float(bonus_obj.value) if bonus_obj and bonus_obj.value else 0.005
                    
                    referrer.balance_store = (referrer.balance_store or 0.0) + bonus_val
                    referrer.referral_earnings = (referrer.referral_earnings or 0.0) + bonus_val
                    referrer.refer_count = (referrer.refer_count or 0) + 1
                    
                    # Merge user into this session to update the flag
                    user = await ref_session.merge(user)
                    user.referral_bonus_awarded = True
                    
                    txn = Transaction(user_id=referrer_id, type=TransactionType.REFERRAL, amount=bonus_val)
                    ref_session.add(txn)
                    
                    await ref_session.commit()
                    logger.info(f"Referral Awarded: User {user_id} joined via {referrer_id}, awarded ${bonus_val}")

                    # Notify referrer
                    try:
                        target_bot = bot or message.bot
                        formatted_bonus = f"{bonus_val:.3f}" if f"{bonus_val:.3f}"[-1] != '0' else f"{bonus_val:.2f}"
                        
                        if referrer.language == 'ar':
                            msg_text = f"🎁 لقد ربحت <b>${formatted_bonus}</b> من إحالة جديدة!"
                        else:
                            msg_text = f"🎁 You earned <b>${formatted_bonus}</b> from a new referral!"
                            
                        await target_bot.send_message(referrer_id, msg_text, parse_mode="HTML")
                        logger.info(f"Referral notification sent to {referrer_id}")
                    except Exception as send_err:
                        logger.error(f"Failed to send referral notification to {referrer_id}: {send_err}")
        
        if user and user.is_banned_store:
            from database.models import AppSetting
            support_obj = (await session.execute(select(AppSetting).where(AppSetting.key == "SUPPORT_USERNAME"))).scalar_one_or_none()
            support_username = support_obj.value if support_obj else None
            
            markup = None
            if support_username:
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Contact Support 🎧", url=f"https://t.me/{support_username}")]
                ])
            
            await message.answer("<b>🚫 Your account has been suspended.</b>", parse_mode="HTML", reply_markup=markup)
            return
    
    # Referral and user creation is now handled by UserUpdateMiddleware
    await message.answer(
        "Welcome to the Store! 🛒\nClick the button below to open.",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(lambda c: c.data == "my_referral")
async def cq_my_referral(call: CallbackQuery, bot: Bot):
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == call.from_user.id))).scalar_one_or_none()
        if not user:
            return
            
        refs_count = (await session.execute(select(func.count(User.id)).where(User.referred_by == user.id))).scalar() or 0
        
        # Fetch dynamic settings
        from database.models import AppSetting
        bonus_obj = (await session.execute(select(AppSetting).where(AppSetting.key == "referral_join_bonus"))).scalar_one_or_none()
        comm_obj = (await session.execute(select(AppSetting).where(AppSetting.key == "referral_commission_percent"))).scalar_one_or_none()
        
        bonus_val = float(bonus_obj.value) if bonus_obj and bonus_obj.value else 0.005
        comm_val = float(comm_obj.value) if comm_obj and comm_obj.value else 1.0
        
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=REF{user.id}"
    
    text = (
        "Share your referral link with your friends or channels and earn rewards:\n"
        f"• <b>${bonus_val:.3f if f'{bonus_val:.3f}'[-1] != '0' else bonus_val:.2f}</b> for each person who joins.\n"
        f"• <b>{comm_val}% commission</b> on all their deposits!\n\n"
        f"🔗 <b>Your Link:</b>\n<code>{ref_link}</code>\n\n"
        f"👥 <b>Total Referrals:</b> {refs_count}\n"
        f"💰 <b>Total Earnings:</b> ${user.referral_earnings or 0.0:.3f if f'{user.referral_earnings or 0.0:.3f}'[-1] != '0' else user.referral_earnings or 0.0:.2f}"
    )
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Back 🔙", callback_data="back_main")]
    ])
    
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=markup)

@router.callback_query(lambda c: c.data == "back_main")
async def cq_back_main(call: CallbackQuery):
    await call.message.edit_text(
        "Welcome to the Store! 🛒\nClick the button below to open.",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )
