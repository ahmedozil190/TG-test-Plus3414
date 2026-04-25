import asyncio
from sqlalchemy import text
from database.engine import async_session

async def delete_test_deposits():
    async with async_session() as session:
        try:
            # Delete transactions with TXIDs starting with TEST_TX or having the specific test IDs
            # Also delete based on the specific test IDs I used earlier
            await session.execute(text("DELETE FROM deposits WHERE txid LIKE 'TEST_TX%' OR txid IN ('TEST_TXID_001', 'TEST_TXID_002')"))
            await session.commit()
            print("Successfully deleted test deposits.")
        except Exception as e:
            print(f"Error deleting test deposits: {e}")

if __name__ == "__main__":
    asyncio.run(delete_test_deposits())
