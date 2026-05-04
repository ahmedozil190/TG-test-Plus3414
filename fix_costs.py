import asyncio
from database.engine import async_session
from database.models import Account, ApiServer
from sqlalchemy import select

async def fix():
    async with async_session() as session:
        # Get all external accounts with no locked_buy_price
        accs = (await session.execute(
            select(Account).where(
                Account.server_id.isnot(None),
                Account.locked_buy_price.is_(None)
            )
        )).scalars().all()
        
        # Get all servers
        servers = (await session.execute(select(ApiServer))).scalars().all()
        srv_map = {s.id: s for s in servers}
        
        updated_count = 0
        for acc in accs:
            srv = srv_map.get(acc.server_id)
            if srv:
                # price = cost * (1 + margin / 100)
                # cost = price / (1 + margin / 100)
                margin = srv.profit_margin or 0
                cost = acc.price / (1 + margin / 100.0)
                acc.locked_buy_price = round(cost, 4)
                updated_count += 1
                
        await session.commit()
        print(f"Updated {updated_count} past sales with estimated costs.")

if __name__ == "__main__":
    asyncio.run(fix())
