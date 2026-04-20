
import asyncio
from sqlalchemy import select
from database.engine import async_session
from database.models import User, CountryPrice

async def test_data():
    async with async_session() as session:
        users = (await session.execute(select(User))).scalars().all()
        prices = (await session.execute(select(CountryPrice))).scalars().all()
        
        print(f"Total Users in DB: {len(users)}")
        for u in users:
            print(f"User ID: {u.id}, Banned Store: {u.is_banned_store}")
            
        print(f"Total Prices in DB: {len(prices)}")
        for p in prices:
            print(f"Country: {p.country_code} ({p.country_name}), Store Active: {p.is_active_store}")

if __name__ == "__main__":
    asyncio.run(test_data())
