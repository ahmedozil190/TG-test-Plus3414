
import asyncio
import random
from datetime import datetime
from database.engine import async_session
from database.models import User, Account, AccountStatus
from sqlalchemy import select

async def create_fake_orders():
    async with async_session() as session:
        # Get the first user found
        user = (await session.execute(select(User).limit(1))).scalar()
        if not user:
            print("No user found in database.")
            return

        print(f"Creating 15 fake orders for user: {user.full_name} ({user.id})")
        
        countries = ["Egypt", "UK", "Russia", "Germany", "France"]
        
        for i in range(15):
            acc = Account(
                phone_number=f"+1{random.randint(100000000, 999999999)}",
                country=random.choice(countries),
                session_string="FAKE_SESSION",
                price=random.uniform(0.5, 5.0),
                status=AccountStatus.SOLD,
                buyer_id=user.id,
                created_at=datetime.utcnow()
            )
            session.add(acc)
        
        await session.commit()
        print("Successfully created 15 fake orders.")

if __name__ == "__main__":
    asyncio.run(create_fake_orders())
