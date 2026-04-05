from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.future import select
from database.models import User
from database.engine import async_session
from keyboards.client import main_keyboard

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    async with async_session() as session:
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(id=user_id, balance=0.0)
            session.add(user)
            await session.commit()
            
    await message.answer(
        f"Welcome {message.from_user.full_name} to the Exclusive Numbers Store!\n"
        "Here you can buy Telegram numbers to receive codes, or sell your numbers to us.",
        reply_markup=main_keyboard()
    )
