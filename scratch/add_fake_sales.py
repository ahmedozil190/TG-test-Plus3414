
import asyncio
import random
from datetime import datetime, timedelta
from database.engine import async_session
from database.models import User, Account, AccountStatus
from sqlalchemy.future import select

async def add_fake_sales():
    async with async_session() as session:
        # Get a user id to use as buyer
        user_res = await session.execute(select(User).limit(1))
        user = user_res.scalar()
        buyer_id = user.id if user else 123456789
        
        countries = [
            ("USA", "+1"), ("UK", "+44"), ("Egypt", "+20"), ("UAE", "+971"), 
            ("Germany", "+49"), ("France", "+33"), ("Russia", "+7"), ("Turkey", "+90"),
            ("Saudi Arabia", "+966"), ("Kuwait", "+965")
        ]
        
        new_accounts = []
        for i in range(15):
            country_name, prefix = random.choice(countries)
            phone = f"{prefix}{random.randint(10000000, 99999999)}"
            price = round(random.uniform(0.5, 12.0), 2)
            
            # Stagger the times a bit
            purchased_at = datetime.utcnow() - timedelta(minutes=random.randint(1, 500))
            
            acc = Account(
                phone_number=phone,
                country=country_name,
                session_string="DUMMY_SESSION_STRING",
                status=AccountStatus.SOLD,
                buyer_id=buyer_id,
                price=price,
                seller_id=0,
                purchased_at=purchased_at,
                created_at=purchased_at - timedelta(hours=1)
            )
            session.add(acc)
            
        await session.commit()
        print(f"Added 15 fake sales records for buyer_id {buyer_id}")

if __name__ == "__main__":
    asyncio.run(add_fake_sales())
