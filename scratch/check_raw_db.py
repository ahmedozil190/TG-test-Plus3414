import asyncio
from sqlalchemy import text
from database.engine import engine

async def check():
    async with engine.connect() as conn:
        print("--- All Records in country_prices ---")
        res = await conn.execute(text("SELECT id, country_code, iso_code, country_name FROM country_prices"))
        for row in res:
            print(f"ID: {row[0]}, Code: '{row[1]}' (Type: {type(row[1])}), ISO: '{row[2]}', Name: '{row[3]}'")

if __name__ == "__main__":
    asyncio.run(check())
