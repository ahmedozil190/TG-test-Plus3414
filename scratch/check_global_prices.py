import asyncio
from sqlalchemy.future import select
from database.engine import async_session
from database.models import CountryPrice

async def check():
    async with async_session() as session:
        res = await session.execute(select(CountryPrice))
        rows = res.scalars().all()
        print(f"Total Global Prices: {len(rows)}")
        for r in rows:
            print(f"Code: {r.country_code}, ISO: {r.iso_code}, BuyPrice: {r.buy_price}")

if __name__ == "__main__":
    asyncio.run(check())
