import asyncio
from database.engine import async_session
from database.models import AppSetting
from sqlalchemy import select

async def check():
    async with async_session() as session:
        stmt = select(AppSetting)
        res = await session.execute(stmt)
        for row in res.scalars().all():
            print(f"Key: {row.key} | Value: {row.value}")

if __name__ == "__main__":
    asyncio.run(check())
