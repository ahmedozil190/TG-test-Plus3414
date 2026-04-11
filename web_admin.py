import os
import logging
import traceback
import phonenumbers
from phonenumbers import geocoder
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.future import select
from sqlalchemy import func
from database.engine import async_session
from database.models import User, Account, Transaction, AccountStatus, TransactionType, CountryPrice
from pydantic import BaseModel
from typing import List
from services.session_manager import request_app_code, submit_app_code, login_clients

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Store Admin Panel")

# Use absolute path for templates to avoid issues in deployment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Models for API requests
class StockLoginStart(BaseModel):
    phone: str

class StockLoginComplete(BaseModel):
    phone: str
    code: str
    hash: str
    password: str = None
    country: str
    price: float

class BalanceUpdate(BaseModel):
    user_id: int
    amount: float

class PriceUpdate(BaseModel):
    country_code: str
    country_name: str
    price: float

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

            # Country Prices
            try:
                prices_result = await session.execute(select(CountryPrice).order_by(CountryPrice.country_name))
                prices = [{"code": p.country_code, "name": p.country_name, "price": p.price} for p in prices_result.scalars().all()]
            except Exception as e:
                logger.error(f"Error fetching prices: {e}")
                prices = []

        return {
            "stats": {
                "user_count": user_count,
                "stock_count": stock_count,
                "total_balance": total_balance
            },
            "users": users,
            "accounts": accounts,
            "transactions": transactions,
            "prices": prices
        }
    except Exception as e:
        logger.error(f"Fatal error in get_admin_data: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/stock/start-login")
async def start_login(data: StockLoginStart):
    phone = data.phone
    if not phone.startswith("+"):
        phone = "+" + phone
        
    try:
        parsed = phonenumbers.parse(phone)
        country_code = str(parsed.country_code)
        country_name = geocoder.description_for_number(parsed, "en") or f"Code {country_code}"
    except Exception as e:
        logger.error(f"Phone Parse Error: {e}")
        raise HTTPException(status_code=400, detail="رقم هاتف غير صالح")
        
    async with async_session() as session:
        cp = (await session.execute(select(CountryPrice).where(CountryPrice.country_code == country_code))).scalar()
        price = cp.price if cp else 1.0 # Default fallback
        
    try:
        # Use -1 as a special ID for Admin Login
        code_hash = await request_app_code(-1, phone)
        return {
            "status": "success",
            "country": country_name,
            "price": price,
            "hash": code_hash
        }
    except Exception as e:
        logger.error(f"Login Start Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/stock/complete-login")
async def complete_login(data: StockLoginComplete):
    try:
        # If 2FA is needed, the current session_manager doesn't handle it well in submit_app_code.
        # But for now, we'll try the simple path.
        session_string = await submit_app_code(-1, data.phone, data.hash, data.code)
        
        if not session_string:
            raise HTTPException(status_code=400, detail="فشل في جلب الجلسة. قد يكون الكود خطأ.")
            
        async with async_session() as session:
            new_acc = Account(
                phone_number=data.phone,
                country=data.country,
                price=data.price,
                session_string=session_string,
                status=AccountStatus.AVAILABLE
            )
            session.add(new_acc)
            await session.commit()
            
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Login Complete Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/prices/update")
async def update_price(data: PriceUpdate):
    async with async_session() as session:
        cp = (await session.execute(select(CountryPrice).where(CountryPrice.country_code == data.country_code))).scalar()
        if cp:
            cp.price = data.price
            cp.country_name = data.country_name
        else:
            cp = CountryPrice(country_code=data.country_code, country_name=data.country_name, price=data.price)
            session.add(cp)
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
