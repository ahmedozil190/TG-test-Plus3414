import asyncio
from database.models import Base
from database.engine import engine

async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database migrated successfully.")

if __name__ == "__main__":
    asyncio.run(migrate())
