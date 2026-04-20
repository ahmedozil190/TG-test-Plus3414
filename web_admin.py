import os
import logging
import traceback
import phonenumbers
from phonenumbers import geocoder
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.future import select
from sqlalchemy import select, delete, update, func, text
from database.engine import async_session
from database.models import User, Account, Transaction, AccountStatus, TransactionType, CountryPrice, WithdrawalRequest, WithdrawalStatus
from pydantic import BaseModel
from typing import List
from services.session_manager import request_app_code, submit_app_code, login_clients
import pycountry
import re
import urllib.request
import json
import asyncio
from datetime import datetime
import random
import string

class SellerDataRequest(BaseModel):
    user_id: int

class SellerOTPRequest(BaseModel):
    user_id: int
    phone: str

class SellerOTPSubmit(BaseModel):
    user_id: int
    phone: str
    hash: str
    code: str
    country: str
    buy_price: float

class WithdrawSubmit(BaseModel):
    user_id: int
    amount: float
    method: str
    address: str

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_transaction_id():
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choice(chars) for _ in range(10))
    return f"TC{suffix}"

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
                # pycountry names are clean, but let's ensure no extra codes are appended
                name = country.name
                # Remove common suffixes like "EG", "(EG)", etc.
                name = re.sub(r'\s*\(?[A-Z]{2,3}\)?\s*$', '', name).strip()
        except: pass
        
        return name, flag
    except Exception as e:
        logger.error(f"Error resolving country {country_code_str}: {e}")
        return f"Code {country_code_str}", "🌐"

def clean_display_name(raw_name: str) -> str:
    """Removes trailing ISO codes like EG, (EG), or [EG], and resolves standalone codes."""
    if not raw_name: return raw_name
    
    # Standalone code resolution map
    codes_map = {
        "EG": "Egypt",
        "US": "United States",
        "UK": "United Kingdom",
        "SA": "Saudi Arabia",
        "RU": "Russia",
        "UA": "Ukraine"
    }
    
    # If the name itself is just a code, resolve it
    trimmed = raw_name.strip().upper()
    if trimmed in codes_map:
        return codes_map[trimmed]
    
    # Handle formats like "Egypt EG", "Egypt (EG)", "Egypt [EG]"
    clean = re.sub(r'\s*[\(\[]?[A-Z]{2,3}[\)\]]?\s*$', '', raw_name)
    return clean.strip()

app = FastAPI(title="Store Admin Panel")

@app.get("/seller", response_class=HTMLResponse)
async def get_seller_panel(request: Request):
    return templates.TemplateResponse(request=request, name="seller.html")

@app.on_event("startup")
async def run_migrations():
    """Auto-migrate SQLite DB to add any missing columns."""
    from database.engine import engine
    import sqlalchemy
    try:
        async with engine.begin() as conn:
            # Add full_name to users if missing
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN full_name TEXT"))
            except: pass
            # Add username to users if missing
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN username TEXT"))
            except: pass
            # Add balance_store to users if missing
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN balance_store FLOAT DEFAULT 0.0"))
                # Copy existing balance to balance_store if possible
                try:
                    await conn.execute(sqlalchemy.text("UPDATE users SET balance_store = balance"))
                except: pass
            except: pass
            # Add balance_sourcing to users if missing
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN balance_sourcing FLOAT DEFAULT 0.0"))
            except: pass
            # Add is_active_store to users if missing
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN is_active_store BOOLEAN DEFAULT 0"))
            except: pass
            # Add is_active_sourcing to users if missing
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN is_active_sourcing BOOLEAN DEFAULT 0"))
            except: pass
            # Add is_banned_store to users if missing
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN is_banned_store BOOLEAN DEFAULT 0"))
            except: pass
            # Add is_banned_sourcing to users if missing
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN is_banned_sourcing BOOLEAN DEFAULT 0"))
            except: pass
            
            # One-time migration: set existing users active in both if they weren't before
            # This ensures they appear in dashboards immediately after migration
            try:
                await conn.execute(sqlalchemy.text("UPDATE users SET is_active_store = 1, is_active_sourcing = 1 WHERE is_active_store = 0 AND is_active_sourcing = 0"))
            except: pass

            # Add missing columns to accounts table
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE accounts ADD COLUMN seller_id INTEGER"))
            except: pass
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE accounts ADD COLUMN buyer_id INTEGER"))
            except: pass
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE accounts ADD COLUMN created_at DATETIME"))
            except: pass

            # Add missing columns to country_prices table
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE country_prices ADD COLUMN country_name TEXT"))
            except: pass
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE country_prices ADD COLUMN buy_price FLOAT DEFAULT 0.0"))
            except: pass
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE country_prices ADD COLUMN approve_delay INTEGER DEFAULT 0"))
            except: pass
        logger.info("DB migration check complete.")
    except Exception as e:
        logger.warning(f"Migration warning: {e}")

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
    type: str = "store" # "store" or "sourcing"

class BanToggle(BaseModel):
    user_id: int
    bot_type: str # "store" or "sourcing"
    banned: bool

class PriceUpdate(BaseModel):
    country_code: str
    country_name: str
    price: float
    buy_price: float
    approve_delay: int

class StoreBuy(BaseModel):
    user_id: int
    country: str

class UserSync(BaseModel):
    user_id: int
    bot_type: str # "store" or "sourcing"

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
    return templates.TemplateResponse(request=request, name="admin_store.html")

@app.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/store", response_class=HTMLResponse)
async def store_page(request: Request):
    return templates.TemplateResponse(request=request, name="store.html")

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
                    balance = user.balance_store

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
            if user.balance_store < account.price: raise HTTPException(status_code=400, detail="رصيدك غير كافٍ")
            user.balance_store -= account.price
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
                    "name": f"{flag} {clean_display_name(p.country_name)}", 
                    "buy_price": p.buy_price,
                    "price": p.price,
                    "approve_delay": p.approve_delay
                })

            # Bot-specific user count and balance
            bot_name = "Bot"
            try:
                from config import SELLER_BOT_TOKEN
                def fetch_bot_name():
                    try:
                        req = urllib.request.Request(f"https://api.telegram.org/bot{SELLER_BOT_TOKEN}/getMe")
                        with urllib.request.urlopen(req, timeout=2) as r:
                            res_data = json.loads(r.read().decode())
                            if res_data.get("ok"):
                                return res_data["result"].get("first_name", "Bot")
                    except: return "Bot"
                bot_name = await asyncio.to_thread(fetch_bot_name)
            except Exception as b_err:
                logger.error(f"Error fetching sourcing bot name: {b_err}")

            user_count = (await session.execute(select(func.count(User.id)).where(User.is_active_sourcing == True))).scalar() or 0
            total_sourcing_balance = (await session.execute(select(func.sum(User.balance_sourcing)))).scalar() or 0.0

            # NEW: Sourcing User List
            users_result = await session.execute(select(User).where(User.is_active_sourcing == True).order_by(User.id.desc()).limit(200))
            active_users = users_result.scalars().all()
            
            # Get seller stats for these users
            u_ids = [u.id for u in active_users]
            seller_stats = {uid: {"sold": 0, "accepted": 0, "rejected": 0} for uid in u_ids}
            if u_ids:
                sold_stmt = select(Account.seller_id, func.count(Account.id)).where(Account.seller_id.in_(u_ids), Account.status == AccountStatus.SOLD).group_by(Account.seller_id)
                acc_stmt = select(Account.seller_id, func.count(Account.id)).where(Account.seller_id.in_(u_ids), Account.status == AccountStatus.AVAILABLE).group_by(Account.seller_id)
                rej_stmt = select(Account.seller_id, func.count(Account.id)).where(Account.seller_id.in_(u_ids), Account.status == AccountStatus.REJECTED).group_by(Account.seller_id)
                
                for rid, cnt in (await session.execute(sold_stmt)).all(): seller_stats[rid]["sold"] = cnt
                for rid, cnt in (await session.execute(acc_stmt)).all(): seller_stats[rid]["accepted"] = cnt
                for rid, cnt in (await session.execute(rej_stmt)).all(): seller_stats[rid]["rejected"] = cnt

            users_list = []
            for u in active_users:
                users_list.append({
                    "id": u.id,
                    "full_name": u.full_name or "N/A",
                    "username": f"@{u.username}" if u.username else "N/A",
                    "balance_sourcing": round(u.balance_sourcing or 0.0, 2),
                    "join_date": u.join_date.strftime("%Y-%m-%d") if u.join_date else "N/A",
                    "banned": u.is_banned_sourcing,
                    "sold_count": seller_stats[u.id]["sold"],
                    "accepted_count": seller_stats[u.id]["accepted"],
                    "rejected_count": seller_stats[u.id]["rejected"]
                })

            return {
                "bot_name": bot_name,
                "stats": {
                    "total_sourced": total_sourced, 
                    "pending_count": pending_count,
                    "total_balance": round(total_sourcing_balance, 2),
                    "user_count": user_count
                },
                "recent": recent,
                "prices": prices,
                "users": users_list
            }
    except Exception as e:
        logger.error(f"Sourcing Data Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/store/data")
async def get_admin_store_data():
    try:
        async with async_session() as session:
            bot_name = "Bot"
            try:
                from config import BOT_TOKEN
                def fetch_bot_name_store():
                    try:
                        req = urllib.request.Request(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe")
                        with urllib.request.urlopen(req, timeout=2) as r:
                            res_data = json.loads(r.read().decode())
                            if res_data.get("ok"):
                                return res_data["result"].get("first_name", "Bot")
                    except: return "Bot"
                bot_name = await asyncio.to_thread(fetch_bot_name_store)
            except Exception as b_err:
                logger.error(f"Error fetching store bot name: {b_err}")

            user_count = (await session.execute(select(func.count(User.id)).where(User.is_active_store == True))).scalar() or 0
            stock_count = (await session.execute(select(func.count(Account.id)).where(Account.status == AccountStatus.AVAILABLE))).scalar() or 0
            total_balance = (await session.execute(select(func.sum(User.balance_store)))).scalar() or 0.0

            users_result = await session.execute(select(User).where(User.is_active_store == True).order_by(User.id.desc()).limit(200))
            all_users_raw = users_result.scalars().all()

            # Get per-user account stats in one query
            seller_stats = {}
            for u in all_users_raw:
                sold = (await session.execute(
                    select(func.count(Account.id)).where(Account.seller_id == u.id)
                )).scalar() or 0
                accepted = (await session.execute(
                    select(func.count(Account.id)).where(
                        Account.seller_id == u.id,
                        Account.status == AccountStatus.SOLD
                    )
                )).scalar() or 0
                rejected = (await session.execute(
                    select(func.count(Account.id)).where(
                        Account.seller_id == u.id,
                        Account.status == AccountStatus.REJECTED
                    )
                )).scalar() or 0
                bought = (await session.execute(
                    select(func.count(Account.id)).where(Account.buyer_id == u.id)
                )).scalar() or 0
                # Total spent (sum of TransactionType.BUY amounts)
                spent = (await session.execute(
                    select(func.sum(Transaction.amount)).where(
                        Transaction.user_id == u.id,
                        Transaction.type == TransactionType.BUY
                    )
                )).scalar() or 0.0
                
                seller_stats[u.id] = {
                    "sold": sold, "accepted": accepted,
                    "rejected": rejected, "bought": bought,
                    "spent": abs(spent)
                }

            users = [
                {
                    "id": u.id,
                    "full_name": u.full_name or "N/A",
                    "username": f"@{u.username}" if u.username else "N/A",
                    "balance_store": round(u.balance_store or 0.0, 2),
                    "balance_sourcing": round(u.balance_sourcing or 0.0, 2),
                    "join_date": u.join_date.strftime("%Y-%m-%d") if u.join_date else "N/A",
                    "banned": u.is_banned_store,
                    "sold_count": seller_stats[u.id]["sold"],
                    "accepted_count": seller_stats[u.id]["accepted"],
                    "rejected_count": seller_stats[u.id]["rejected"],
                    "bought_count": seller_stats[u.id]["bought"],
                    "spent_total": round(seller_stats[u.id]["spent"], 2),
                }
                for u in all_users_raw
            ]
            
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
                    "name": f"{flag} {clean_display_name(p.country_name)}",
                    "price": p.price
                })

        return {
            "bot_name": bot_name,
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
            if data.type == "sourcing":
                user.balance_sourcing = data.amount
            else:
                user.balance_store = data.amount
            await session.commit()
            return {"status": "success"}
    raise HTTPException(status_code=404, detail="User not found")

@app.post("/api/admin/user/toggle-ban")
async def toggle_ban(data: BanToggle):
    async with async_session() as session:
        user = await session.get(User, data.user_id)
        if user:
            if data.bot_type == "sourcing":
                user.is_banned_sourcing = data.banned
            else:
                user.is_banned_store = data.banned
            await session.commit()
            return {"status": "success"}
    raise HTTPException(status_code=404, detail="User not found")
# --- Seller Panel APIs ---

@app.get("/api/seller/data")
async def get_seller_data(user_id: int):
    try:
        async with async_session() as session:
            user = await session.get(User, user_id)
            if not user:
                # Create user if missing (first time opening app)
                user = User(id=user_id, balance_sourcing=0.0, balance_store=0.0, is_active_sourcing=True)
                session.add(user)
                await session.commit()
                await session.refresh(user)
            
            # Fetch Bot Name dynamically
            bot_name = "Bot"
            try:
                from config import SELLER_BOT_TOKEN
                with urllib.request.urlopen(f"https://api.telegram.org/bot{SELLER_BOT_TOKEN}/getMe", timeout=5) as r:
                    res_data = json.loads(r.read().decode())
                    if res_data.get("ok"):
                        bot_name = res_data["result"].get("first_name", "Bot")
            except Exception as b_err:
                logger.error(f"Error fetching bot name: {b_err}")

            # Get stats
            sold_count = (await session.execute(select(func.count(Account.id)).where(Account.seller_id == user_id, Account.status == AccountStatus.SOLD))).scalar() or 0
            pending_count = (await session.execute(select(func.count(Account.id)).where(Account.seller_id == user_id, Account.status == AccountStatus.PENDING))).scalar() or 0
            accepted_count = (await session.execute(select(func.count(Account.id)).where(Account.seller_id == user_id, Account.status == AccountStatus.AVAILABLE))).scalar() or 0
            rejected_count = (await session.execute(select(func.count(Account.id)).where(Account.seller_id == user_id, Account.status == AccountStatus.REJECTED))).scalar() or 0
            
            # Calculate Pending Balance
            pending_balance = (await session.execute(
                select(func.sum(Account.price)).where(Account.seller_id == user_id, Account.status == AccountStatus.PENDING)
            )).scalar() or 0.0
            
            # Calculate Total Withdrawn
            total_withdrawn = (await session.execute(
                select(func.sum(Transaction.amount)).where(Transaction.user_id == user_id, Transaction.type == TransactionType.WITHDRAW)
            )).scalar() or 0.0
            
            # Get prices
            prices_result = await session.execute(select(CountryPrice).where(CountryPrice.buy_price > 0).order_by(CountryPrice.country_name))
            prices = prices_result.scalars().all()
            
            formatted_prices = []
            for p in prices:
                try:
                    name, flag = resolve_country_info(p.country_code)
                    formatted_prices.append({
                        "name": p.country_name if p.country_name and p.country_name != "Unknown" else name,
                        "flag": flag,
                        "code": p.country_code,
                        "price": p.buy_price
                    })
                except Exception as inner_e:
                    logger.error(f"Error processing price for code {p.country_code}: {inner_e}")
                
            return {
                "user": {
                    "id": user.id,
                    "balance": user.balance_sourcing,
                    "pending_balance": pending_balance,
                    "total_withdrawn": total_withdrawn,
                    "is_banned": user.is_banned_sourcing
                },
                "bot_name": bot_name,
                "stats": {
                    "sold": sold_count,
                    "pending": pending_count,
                    "accepted": accepted_count,
                    "rejected": rejected_count
                },
                "prices": formatted_prices
            }
    except Exception as e:
        logger.error(f"Seller Data API Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"خطأ برمي: {str(e)}")

@app.post("/api/seller/request-otp")
async def seller_request_otp(data: SellerOTPRequest):
    async with async_session() as session:
        user = await session.get(User, data.user_id)
        if user and user.is_banned_sourcing:
            raise HTTPException(status_code=403, detail="عذراً، أنت محظور من التوريد.")
            
    try:
        phone = data.phone.strip()
        if not phone.startswith("+"): phone = "+" + phone
        
        # Pre-check 1: Duplicity
        async with async_session() as session:
            dup_stmt = select(Account).where(Account.phone_number == phone)
            existing = (await session.execute(dup_stmt)).scalar()
            if existing:
                raise HTTPException(status_code=400, detail="This account already exists in the system.")

        # Pre-check 2: Country availability
        try:
            parsed = phonenumbers.parse(phone)
            cc = str(parsed.country_code)
            async with async_session() as session:
                cp_stmt = select(CountryPrice).where(CountryPrice.country_code == cc)
                cp = (await session.execute(cp_stmt)).scalar()
                if not cp:
                    raise HTTPException(status_code=400, detail="Sorry, this country is not requested at the moment.")
        except HTTPException as he: raise he
        except: 
            raise HTTPException(status_code=400, detail="Invalid phone number format.")

        phone_code_hash = await request_app_code(data.user_id, phone)
        return {"hash": phone_code_hash, "phone": phone}
    except Exception as e:
        logger.error(f"Seller OTP Request Error: {e}")
        if isinstance(e, HTTPException): raise e
        # Map specific exceptions from session_manager
        err_msg = str(e)
        if "banned" in err_msg.lower() or "frozen" in err_msg.lower():
             raise HTTPException(status_code=400, detail=err_msg)
        raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")

@app.post("/api/seller/submit-otp")
async def seller_submit_otp(data: SellerOTPSubmit):
    try:
        session_string = await submit_app_code(data.user_id, data.phone, data.hash, data.code)
        
        if not session_string:
            raise HTTPException(status_code=400, detail="Verification failed. The code is incorrect or has expired.")
            
        async with async_session() as session:
            # Automatic price detection
            price = 0
            try:
                parsed = phonenumbers.parse(data.phone if data.phone.startswith("+") else "+" + data.phone)
                cc = str(parsed.country_code)
                cp_stmt = select(CountryPrice).where(CountryPrice.country_code == cc)
                cp = (await session.execute(cp_stmt)).scalar()
                if cp: price = cp.buy_price
            except: pass

            new_acc = Account(
                phone_number=data.phone,
                country=data.country,
                price=price,
                session_string=session_string,
                status=AccountStatus.PENDING,
                seller_id=data.user_id,
                created_at=datetime.utcnow()
            )
            session.add(new_acc)
            await session.commit()
            
        return {"status": "success", "price": price}
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        logger.error(f"Seller OTP Submit Error: {e}")
        err_msg = str(e)
        if any(msg in err_msg.lower() for msg in ["restricted", "frozen", "security check"]):
            raise HTTPException(status_code=400, detail=err_msg)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/clear-accounts-system")
async def clear_accounts_admin(key: str):
    # This is a temporary tool to help you clear test data from Railway
    MASTER_KEY = "clear12399"
    if key != MASTER_KEY:
        return {"error": "Invalid master key"}
        
    async with async_session() as session:
        try:
            await session.execute(text("DELETE FROM accounts"))
            await session.commit()
            return {"status": "Success", "message": "All sourcing history has been cleared from the live server."}
        except Exception as e:
            return {"status": "Error", "message": str(e)}

@app.post("/api/seller/withdraw")
async def seller_withdraw(req: WithdrawSubmit):
    async with async_session() as session:
        user = await session.get(User, req.user_id)
        if not user or not user.is_active_sourcing:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Validation: Check amount and balance
        if req.amount <= 0:
            raise HTTPException(status_code=400, detail="Invalid amount")
            
        min_amount = 4.0 if "TRX" in req.method else 10.0
        if req.amount < min_amount:
            raise HTTPException(status_code=400, detail=f"Minimum withdrawal is ${min_amount}")
        
        if user.balance_sourcing < req.amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        
        if req.amount <= 0.20:
            raise HTTPException(status_code=400, detail="Amount too low to cover fees")

        # Create Request
        tid = generate_transaction_id()
        withdraw = WithdrawalRequest(
            user_id=req.user_id,
            amount=req.amount,
            method=req.method,
            address=req.address,
            transaction_id=tid
        )
        
        # Deduct balance immediately
        user.balance_sourcing -= req.amount
        
        session.add(withdraw)
        await session.commit()
        await session.refresh(withdraw)
        return {"ok": True, "id": tid}

@app.get("/api/seller/withdrawals")
async def get_withdrawals(user_id: int, page: int = 1):
    page_size = 10
    offset = (page - 1) * page_size
    async with async_session() as session:
        # Get total count for pagination
        count_stmt = select(func.count(WithdrawalRequest.id)).where(WithdrawalRequest.user_id == user_id)
        total_count = (await session.execute(count_stmt)).scalar() or 0
        total_pages = (total_count + page_size - 1) // page_size

        # Get page data
        stmt = select(WithdrawalRequest).where(WithdrawalRequest.user_id == user_id).order_by(WithdrawalRequest.created_at.desc()).offset(offset).limit(page_size)
        results = (await session.execute(stmt)).scalars().all()
        
        history = []
        for r in results:
            history.append({
                "id": r.id,
                "transaction_id": r.transaction_id,
                "amount": r.amount,
                "method": r.method,
                "address": r.address,
                "status": r.status.value,
                "date": r.created_at.strftime("%Y-%m-%d")
            })
        return {
            "history": history,
            "total_pages": total_pages,
            "current_page": page,
            "total_count": total_count
        }

@app.get("/api/seller/detect-country")
async def detect_country(phone: str):
    try:
        if not phone.startswith("+"): phone = "+" + phone
        parsed = phonenumbers.parse(phone)
        country_code = str(parsed.country_code)
        iso_code = phonenumbers.region_code_for_number(parsed)
        
        async with async_session() as session:
            stmt = select(CountryPrice).where(CountryPrice.country_code == country_code)
            cp = (await session.execute(stmt)).scalar()
            
            if cp:
                return {
                    "found": True,
                    "name": cp.country_name,
                    "flag": get_flag_emoji(iso_code) if iso_code else "🌐",
                    "price": cp.buy_price
                }
    except:
        pass
    return {"found": False}

@app.get("/api/seller/accounts")
async def get_seller_accounts(user_id: int):
    async with async_session() as session:
        stmt = select(Account).where(Account.seller_id == user_id).order_by(Account.created_at.desc()).limit(15)
        results = (await session.execute(stmt)).scalars().all()
        return {
            "accounts": [{
                "phone": a.phone_number,
                "status": a.status.value,
                "date": a.created_at.strftime("%Y-%m-%d %H:%M")
            } for a in results]
        }

@app.post("/api/admin/user/sync")
async def sync_user_identity(data: UserSync):
    try:    
        # 1. Select the correct bot based on bot_type
        bot = app.state.bot_buyer if data.bot_type == "store" else app.state.bot_seller
        
        if not bot:
            raise HTTPException(status_code=500, detail="Bot instance not found for sync")
            
        # 2. Fetch latest data from Telegram
        chat = await bot.get_chat(data.user_id)
        
        # 3. Format name and username
        new_full_name = f"{chat.first_name or ''} {chat.last_name or ''}".strip() or "N/A"
        new_username = chat.username or None
        
        # 4. Update Database
        async with async_session() as session:
            user = await session.get(User, data.user_id)
            if user:
                user.full_name = new_full_name
                user.username = new_username
                await session.commit()
                
                return {
                    "status": "success",
                    "full_name": new_full_name,
                    "username": f"@{new_username}" if new_username else "N/A"
                }
        
        raise HTTPException(status_code=404, detail="User not found in database")
        
    except Exception as e:
        logger.error(f"Identity Sync Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- End of Web Admin SOURCINGPRO ---
