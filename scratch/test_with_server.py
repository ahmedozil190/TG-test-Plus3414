import asyncio
import logging
from sqlalchemy import select
from database.engine import async_session, init_db
from database.models import ApiServer, Account, AccountStatus
from web_admin import get_store_data

async def test():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    async with async_session() as session:
        # Add local stock
        acc = Account(phone_number="123456", country="Egypt", price=1.0, status=AccountStatus.AVAILABLE)
        session.add(acc)
        
        # Add a server
        srv = ApiServer(name="Max-TG", url="https://www.max-tg.com/sub/api/", api_key="i56xdjt45pr9x7j00udm", profit_margin=20.0)
        session.add(srv)
        await session.commit()
        
    try:
        print("\n--- CALLING GET_STORE_DATA ---")
        data = await get_store_data()
        print("\n--- STORE DATA RESULT ---")
        print(f"Countries count: {len(data['countries'])}")
        for c in data['countries']:
            print(f"- {c['name']}: {c['count']}")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
