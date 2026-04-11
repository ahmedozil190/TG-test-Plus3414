import os
import logging
import traceback
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.future import select
from sqlalchemy import func
from database.engine import async_session
from database.models import User, Account, Transaction, AccountStatus, TransactionType
from pydantic import BaseModel
from typing import List

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Store Admin Panel")

# Use absolute path for templates to avoid issues in deployment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Models for API requests
class StockAdd(BaseModel):
    phone: str
    country: str
    price: float
    session: str

class BalanceUpdate(BaseModel):
    user_id: int
    amount: float

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    try:
        return templates.TemplateResponse(request=request, name="dashboard.html", context={})
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        logger.error(traceback.format_exc())
        return HTMLResponse(content=f"<h1>Internal Server Error</h1><pre>{e}</pre>", status_code=500)

@app.get("/api/admin/data")
async def get_admin_data():
    try:
        async with async_session() as session:
            # Stats (with fallbacks)
            try:
                user_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
                stock_count = (await session.execute(select(func.count(Account.id)).where(Account.status == AccountStatus.AVAILABLE))).scalar() or 0
                total_balance = (await session.execute(select(func.sum(User.balance)))).scalar() or 0.0
            except Exception as e:
                logger.error(f"Error fetching stats: {e}")
                user_count, stock_count, total_balance = 0, 0, 0.0

            # Recent Accounts
            try:
                accounts_result = await session.execute(select(Account).where(Account.status == AccountStatus.AVAILABLE).order_by(Account.id.desc()).limit(50))
                accounts = [{"id": a.id, "phone_number": a.phone_number, "country": a.country, "price": a.price} for a in accounts_result.scalars().all()]
            except Exception as e:
                logger.error(f"Error fetching accounts: {e}")
                accounts = []

            # Users
            try:
                users_result = await session.execute(select(User).order_by(User.join_date.desc()).limit(50))
                users = [{"id": u.id, "balance": u.balance, "join_date": u.join_date.strftime("%Y-%m-%d")} for u in users_result.scalars().all()]
            except Exception as e:
                logger.error(f"Error fetching users: {e}")
                users = []
            
            # Recent Transactions
            try:
                tx_result = await session.execute(
                    select(Transaction)
                    .where(Transaction.type == TransactionType.BUY)
                    .order_by(Transaction.timestamp.desc())
                    .limit(10)
                )
                transactions = []
                for tx in tx_result.scalars().all():
                    transactions.append({
                        "buyer_id": tx.user_id,
                        "phone_number": "Account Purchase",
                        "country": "-",
                        "price": abs(tx.amount),
                        "date": tx.timestamp.strftime("%Y-%m-%d %H:%M")
                    })
            except Exception as e:
                logger.error(f"Error fetching transactions: {e}")
                transactions = []

        return {
            "stats": {
                "user_count": user_count,
                "stock_count": stock_count,
                "total_balance": total_balance
            },
            "users": users,
            "accounts": accounts,
            "transactions": transactions
        }
    except Exception as e:
        logger.error(f"Fatal error in get_admin_data: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/stock/add")
async def add_stock(data: StockAdd):
    async with async_session() as session:
        new_acc = Account(
            phone_number=data.phone,
            country=data.country,
            price=data.price,
            session_string=data.session,
            status=AccountStatus.AVAILABLE
        )
        session.add(new_acc)
        await session.commit()
    return {"status": "success"}

@app.delete("/api/admin/stock/delete/{acc_id}")
async def delete_stock(acc_id: int):
    async with async_session() as session:
        acc = await session.get(Account, acc_id)
        if acc:
            await session.delete(acc)
            await session.commit()
    return {"status": "success"}

@app.post("/api/admin/user/balance")
async def update_balance(data: BalanceUpdate):
    async with async_session() as session:
        user = await session.get(User, data.user_id)
        if user:
            user.balance = data.amount
            await session.commit()
            return {"status": "success"}
    raise HTTPException(status_code=404, detail="User not found")
