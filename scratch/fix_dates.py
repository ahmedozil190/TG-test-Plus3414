
import asyncio
import aiosqlite
import os

async def fix_null_dates():
    db_path = "app.db"
    if not os.path.exists(db_path):
        return

    async with aiosqlite.connect(db_path) as db:
        print("Updating NULL purchased_at values to created_at...")
        await db.execute("UPDATE accounts SET purchased_at = created_at WHERE status = 'SOLD' AND purchased_at IS NULL")
        await db.commit()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(fix_null_dates())
