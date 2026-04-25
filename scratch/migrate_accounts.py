
import asyncio
import aiosqlite
import os

async def migrate():
    db_path = "app.db"
    if not os.path.exists(db_path):
        print("Database file not found.")
        return

    async with aiosqlite.connect(db_path) as db:
        # Check if columns exist
        cursor = await db.execute("PRAGMA table_info(accounts)")
        columns = await cursor.fetchall()
        column_names = [c[1] for c in columns]

        if "purchased_at" not in column_names:
            print("Adding purchased_at column to accounts table...")
            await db.execute("ALTER TABLE accounts ADD COLUMN purchased_at DATETIME")
            await db.commit()
            print("Done.")
        else:
            print("purchased_at column already exists.")

if __name__ == "__main__":
    asyncio.run(migrate())
