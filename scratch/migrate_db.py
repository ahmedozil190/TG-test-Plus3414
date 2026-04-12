import asyncio
import sqlalchemy
from database.engine import engine

async def run_migrations():
    print("Checking for missing columns...")
    try:
        async with engine.begin() as conn:
            # Add full_name to users if missing
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN full_name TEXT"))
                print("Column 'full_name' added successfully.")
            except Exception as e:
                print(f"Skipping 'full_name': {e}")
                
            # Add username to users if missing
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN username TEXT"))
                print("Column 'username' added successfully.")
            except Exception as e:
                print(f"Skipping 'username': {e}")
        print("Migration check complete.")
    except Exception as e:
        print(f"Migration error: {e}")

if __name__ == "__main__":
    asyncio.run(run_migrations())
