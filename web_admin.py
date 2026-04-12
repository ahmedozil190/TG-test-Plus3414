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
import pycountry

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_flag_emoji(country_code: str):
    """Convert ISO country code to flag emoji."""
    if not country_code or len(country_code) != 2:
        return "🌐"
    return "".join(chr(ord(c) + 127397) for c in country_code.upper())

def resolve_country_info(country_code_str: str):
    """Resolve ISO code and Country Name from a numeric calling code."""
    try:
        # Clean input: remove +, leading zeros, spaces
        code = country_code_str.strip().lstrip('+').lstrip('0')
        if not code: return "Unknown", "🌐"
        
        numeric_code = int(code)
        iso_code = phonenumbers.region_code_for_country_code(numeric_code)
        flag = get_flag_emoji(iso_code)
        
        # Resolve name using pycountry for accuracy
        name = f"Country {numeric_code}"
        try:
            country = pycountry.countries.get(alpha_2=iso_code)
            if country:
                name = country.name
        except: pass
        
        return name, flag
    except Exception as e:
        logger.error(f"Error resolving country {country_code_str}: {e}")
        return f"Code {country_code_str}", "🌐"

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
    buy_price: float
    approve_delay: int

class StoreBuy(BaseModel):
    user_id: int
    country: str

@app.get("/admin/sourcing", response_class=HTMLResponse)
async def admin_sourcing(request: Request):
    try:
        return templates.TemplateResponse(request=request, name="admin_sourcing.html", context={})
    except Exception as e:
        logger.error(f"Error rendering sourcing dashboard: {e}")
        return HTMLResponse(content=f"<h1>Error</h1><pre>{e}</pre>", status_code=500)

@app.get("/admin/store", response_class=HTMLResponse)
async def admin_store(request: Request):
    try:
        return templates.TemplateResponse(request=request, name="admin_store.html", context={})
    except Exception as e:
        logger.error(f"Error rendering store dashboard: {e}")
        return HTMLResponse(content=f"<h1>Error</h1><pre>{e}</pre>", status_code=500)

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    # Backward compatibility: Redirect to the new store admin by default
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/admin/store")

@app.get("/store", response_class=HTMLResponse)
async def client_store(request: Request):
    try:
        return templates.TemplateResponse(request=request, name="store.html", context={})
    except Exception as e:
        logger.error(f"Error rendering store: {e}")
        return HTMLResponse(content=f"<h1>Internal Server Error</h1><pre>{e}</pre>", status_code=500)

@app.get("/api/store/data")
async def get_store_data(user_id: int = None):
    try:
        async with async_session() as session:
            # Group available accounts by country
            stmt = select(Account.country, Account.price, func.count(Account.id).label('cnt')).where(
                Account.status == AccountStatus.AVAILABLE
            ).group_by(Account.country, Account.price)
            
            results = (await session.execute(stmt)).all()
            
            countries = []
            for row in results:
                name, price, count = row
                # Get flag
                flag = "🌐"
                try:
                    # Look up by name or find a region
                    # For simplicity, we can parse a dummy number if we had one, 
                    # but let's just find the price entry or name match
                    cp = (await session.execute(select(CountryPrice).where(CountryPrice.country_name == name))).scalar()
                    if cp:
                        region = phonenumbers.region_code_for_country_code(int(cp.country_code))
                        flag = get_flag_emoji(region)
                except: pass
                
                countries.append({
                    "name": name,
                    "flag": flag,
                    "price": price,
                    "count": count
                })
            
            # User balance
            balance = 0.0
            if user_id:
                user = await session.get(User, user_id)
                if user:
                    balance = user.balance

        return {
            "countries": countries,
            "user": {"balance": balance}
        }
    except Exception as e:
        logger.error(f"Store Data Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/store/buy")
async def store_buy(data: StoreBuy):
    try:
        async with async_session() as session:
            user = await session.get(User, data.user_id)
            if not user: raise HTTPException(status_code=404, detail="User not found")
            stmt = select(Account).where(Account.country == data.country, Account.status == AccountStatus.AVAILABLE).limit(1)
            account = (await session.execute(stmt)).scalar_one_or_none()
            if not account: raise HTTPException(status_code=400, detail="عذراً، نفدت الأرقام!")
            if user.balance < account.price: raise HTTPException(status_code=400, detail="رصيدك غير كافٍ")
            user.balance -= account.price
            account.status = AccountStatus.SOLD
            account.buyer_id = user.id
            txn = Transaction(user_id=user.id, type=TransactionType.BUY, amount=-account.price)
            session.add(txn)
            await session.commit()
            return {"status": "success", "phone": account.phone_number, "id": account.id}
    except HTTPException as e: raise e
    except Exception as e:
        logger.error(f"Store Buy Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/sourcing/data")
async def get_sourcing_data():
    try:
        async with async_session() as session:
            total_sourced = (await session.execute(select(func.count(Account.id)))).scalar() or 0
            pending_count = (await session.execute(select(func.count(Account.id)).where(Account.status == AccountStatus.PENDING))).scalar() or 0
            
            recent_result = await session.execute(
                select(Account).order_by(Account.id.desc()).limit(20)
            )
            recent = []
            for a in recent_result.scalars().all():
                flag = "🌐"
                try:
                    p = phonenumbers.parse(a.phone_number)
                    flag = get_flag_emoji(phonenumbers.region_code_for_number(p))
                except: pass
                
                # Fetch buy_price simplified
                recent.append({
                    "phone": a.phone_number,
                    "country": f"{flag} {a.country}",
                    "buy_price": a.price * 0.5, # Simplified logic if CP not found
                    "status": a.status.name
                })

            prices_result = await session.execute(
                select(CountryPrice)
                .where(CountryPrice.buy_price > 0)
                .order_by(CountryPrice.country_name)
            )
            prices = []
            for p in prices_result.scalars().all():
                flag = "🌐"
                try:
                    region = phonenumbers.region_code_for_country_code(int(p.country_code))
                    flag = get_flag_emoji(region)
                except: pass
                prices.append({
                    "code": p.country_code, 
                    "name": f"{flag} {p.country_name}", 
                    "buy_price": p.buy_price,
                    "price": p.price,
                    "approve_delay": p.approve_delay
                })

        return {
            "stats": {"total_sourced": total_sourced, "pending_count": pending_count},
            "recent": recent,
            "prices": prices
        }
    except Exception as e:
        logger.error(f"Sourcing Data Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/store/data")
async def get_admin_store_data():
    try:
        async with async_session() as session:
            user_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
            stock_count = (await session.execute(select(func.count(Account.id)).where(Account.status == AccountStatus.AVAILABLE))).scalar() or 0
            total_balance = (await session.execute(select(func.sum(User.balance)))).scalar() or 0.0

            users_result = await session.execute(select(User).order_by(User.join_date.desc()).limit(50))
            users = [{"id": u.id, "balance": u.balance, "join_date": u.join_date.strftime("%Y-%m-%d")} for u in users_result.scalars().all()]
            
            tx_result = await session.execute(
                select(Transaction)
                .where(Transaction.type == TransactionType.BUY)
                .order_by(Transaction.timestamp.desc())
                .limit(20)
            )
            transactions = []
            for tx in tx_result.scalars().all():
                transactions.append({"buyer_id": tx.user_id, "price": abs(tx.amount)})

            # Fetch sell prices only (price > 0 means it's configured for selling)
            prices_result = await session.execute(
                select(CountryPrice)
                .where(CountryPrice.price > 0)
                .order_by(CountryPrice.country_name)
            )
            prices = []
            for p in prices_result.scalars().all():
                flag = "🌐"
                try:
                    region = phonenumbers.region_code_for_country_code(int(p.country_code))
                    flag = get_flag_emoji(region)
                except: pass
                prices.append({
                    "code": p.country_code,
                    "name": f"{flag} {p.country_name}",
                    "price": p.price
                })

        return {
            "stats": {"user_count": user_count, "stock_count": stock_count, "total_balance": total_balance},
            "users": users,
            "transactions": transactions,
            "prices": prices
        }
    except Exception as e:
        logger.error(f"Store Admin Data Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/stock/start-login")
async def start_login(data: StockLoginStart):
    phone = data.phone
    if not phone.startswith("+"):
        phone = "+" + phone
        
    try:
        parsed = phonenumbers.parse(phone)
        country_code = str(parsed.country_code)
        iso_code = phonenumbers.region_code_for_number(parsed)
        flag = get_flag_emoji(iso_code)
        country_name = f"{flag} " + (geocoder.description_for_number(parsed, "en") or f"Code {country_code}")
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

@app.post("/api/admin/sourcing/price/update")
async def update_sourcing_price(data: dict):
    # data: {country_code, buy_price, approve_delay}
    code = data.get("country_code")
    buy_p = float(data.get("buy_price", 0))
    delay = int(data.get("approve_delay", 0))

    # Auto-detect name more reliably
    name_only, _ = resolve_country_info(code)

    async with async_session() as session:
        cp = (await session.execute(select(CountryPrice).where(CountryPrice.country_code == code))).scalar()
        if cp:
            cp.buy_price = buy_p
            cp.approve_delay = delay
            cp.country_name = name_only
        else:
            cp = CountryPrice(
                country_code=code, 
                country_name=name_only, 
                price=0,
                buy_price=buy_p,
                approve_delay=delay
            )
            session.add(cp)
        await session.commit()
    return {"status": "success"}

@app.delete("/api/admin/prices/delete/{code}")
async def delete_price_entry(code: str):
    async with async_session() as session:
        cp = (await session.execute(select(CountryPrice).where(CountryPrice.country_code == code))).scalar()
        if cp:
            await session.delete(cp)
            await session.commit()
            return {"status": "success"}
    raise HTTPException(status_code=404, detail="Price entry not found")

@app.post("/api/admin/prices/update")
async def update_price(data: PriceUpdate):
    """General update (mostly used by Store admin now)"""
    async with async_session() as session:
        cp = (await session.execute(select(CountryPrice).where(CountryPrice.country_code == data.country_code))).scalar()
        if cp:
            cp.price = data.price
            # If name is Unknown, try to resolve it
            if not data.country_name or data.country_name == "Unknown":
                name, _ = resolve_country_info(data.country_code)
                cp.country_name = name
            elif data.country_name:
                cp.country_name = data.country_name
                
            cp.buy_price = data.buy_price
            cp.approve_delay = data.approve_delay
        else:
            name = data.country_name
            if not name or name == "Unknown":
                name, _ = resolve_country_info(data.country_code)
                
            cp = CountryPrice(
                country_code=data.country_code, 
                country_name=name, 
                price=data.price,
                buy_price=data.buy_price,
                approve_delay=data.approve_delay
            )
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
