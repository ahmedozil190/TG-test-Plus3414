import asyncio
from datetime import datetime
from database.models import Deposit
from database.engine import async_session, init_db

async def create_test_deposits():
    # 1. Ensure table exists
    await init_db()
    
    user_id = 8741285999 # The user ID from logs
    async with async_session() as session:
        # Deposit 1
        dep1 = Deposit(
            user_id=user_id,
            amount=10.0,
            txid="TEST_TXID_001",
            method="Binance Pay",
            created_at=datetime.utcnow()
        )
        # Deposit 2
        dep2 = Deposit(
            user_id=user_id,
            amount=25.5,
            txid="TEST_TXID_002",
            method="TRX (TRC20)",
            created_at=datetime.utcnow()
        )
        
        session.add(dep1)
        session.add(dep2)
        await session.commit()
        print(f"Created 2 test deposits for user {user_id}")

if __name__ == "__main__":
    asyncio.run(create_test_deposits())
