from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from database.engine import async_session
from database.models import CountryPrice
from sqlalchemy.future import select
from config import ADMIN_IDS

router = Router()

@router.message(Command("addcountry"))
async def admin_add_country(message: Message):
    # Check if user is admin
    if message.from_user.id not in ADMIN_IDS:
        return

    # Usage: /addcountry  code  name  buy_price  sell_price  delay
    args = message.text.split()[1:]
    if len(args) < 4:
        await message.answer(
            "<b>⚠️ Usage:</b>\n"
            "<code>/addcountry 20 Egypt 0.5 1.0 0</code>\n\n"
            "Parameters: Code, Name, BuyPrice, SellPrice, [Delay=0]",
            parse_mode="HTML"
        )
        return

    try:
        code = args[0]
        # Allow multi-word name if we join appropriately, but for simplicity:
        name = args[1]
        buy_p = float(args[2])
        sell_p = float(args[3])
        delay = int(args[4]) if len(args) > 4 else 0

        async with async_session() as session:
            # Check if exists
            stmt = select(CountryPrice).where(CountryPrice.country_code == code)
            cp = (await session.execute(stmt)).scalar_one_or_none()
            
            if cp:
                cp.country_name = name
                cp.buy_price = buy_p
                cp.price = sell_p
                cp.approve_delay = delay
                status = "Updated"
            else:
                cp = CountryPrice(
                    country_code=code,
                    country_name=name,
                    buy_price=buy_p,
                    price=sell_p,
                    approve_delay=delay
                )
                session.add(cp)
                status = "Added"
            
            await session.commit()
            await message.answer(f"✅ <b>{status} Successfully:</b>\n- {name} (+{code})\n- Buy: ${buy_p}\n- Sell: ${sell_p}", parse_mode="HTML")
            
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

@router.message(Command("sourcing_stats"))
async def admin_sourcing_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    async with async_session() as session:
        result = await session.execute(select(CountryPrice))
        countries = result.scalars().all()
        
    if not countries:
        await message.answer("No countries configured yet.")
        return
        
    text = "<b>📊 Sourcing Inventory:</b>\n\n"
    for c in countries:
        text += f"- {c.country_name} (+{c.country_code}): Buy ${c.buy_price}\n"
        
    await message.answer(text, parse_mode="HTML")
