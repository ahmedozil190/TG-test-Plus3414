import os
import logging
import math
import traceback
from datetime import datetime, timedelta
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

class WithdrawAction(BaseModel):
    request_id: int
    action: str # 'approve' or 'reject'

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_transaction_id():
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choice(chars) for _ in range(10))
    return f"TC{suffix}"

def get_flag_emoji(country_code: str):
    """Convert ISO country code to flag emoji."""
    try:
        if not country_code or not isinstance(country_code, str) or len(country_code) != 2:
            return "🌐"
        return "".join(chr(ord(c) + 127397) for c in country_code.upper())
    except:
        return "🌐"

def resolve_country_info(country_code_str: str, full_phone: str = None):
    """Resolve ISO code and Country Name. If full_phone is provided, detects specific region."""
    try:
        if full_phone:
            try:
                parsed = phonenumbers.parse(full_phone if full_phone.startswith('+') else f"+{full_phone}")
                iso_code = phonenumbers.region_code_for_number(parsed)
                name = pycountry.countries.get(alpha_2=iso_code).name
                name = re.sub(r'\s*\(?[A-Z]{2,3}\)?\s*$', '', name).strip()
                return name, get_flag_emoji(iso_code), iso_code
            except: pass

        # Fallback to calling code prefix
        code = country_code_str.strip().lstrip('+').lstrip('0')
        if not code: return "Unknown", "🌐", "XX"
        
        numeric_code = int(code)
        # For +1, region_code_for_country_code returns 'US'
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
        
        return name, flag, iso_code
    except Exception as e:
        logger.error(f"Error resolving country {country_code_str}: {e}")
        return f"Code {country_code_str}", "🌐", "XX"

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
    """Auto-migrate SQLite DB to add any missing columns and create new tables."""
    from database.engine import engine
    from database.models import Base
    import sqlalchemy
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
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

            # Add iso_code to user_country_prices if missing
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE user_country_prices ADD COLUMN iso_code TEXT DEFAULT 'XX'"))
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
            
            # Add iso_code to country_prices if missing
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE country_prices ADD COLUMN iso_code TEXT DEFAULT 'XX'"))
            except: pass
            
            # Drop unique constraint on country_code if it exists (SQLite workaround requires rebuilding table)
            try:
                table_sql_res = await conn.execute(sqlalchemy.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='country_prices'"))
                table_sql = table_sql_res.scalar()
                if table_sql and 'UNIQUE' in table_sql.upper():
                    logger.info("Rebuilding country_prices to remove UNIQUE constraint")
                    await conn.execute(sqlalchemy.text("""
                        CREATE TABLE country_prices_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            country_code VARCHAR NOT NULL,
                            iso_code VARCHAR DEFAULT 'XX',
                            country_name VARCHAR NOT NULL,
                            price FLOAT NOT NULL DEFAULT 1.0,
                            buy_price FLOAT NOT NULL DEFAULT 0.5,
                            approve_delay INTEGER NOT NULL DEFAULT 0,
                            updated_at DATETIME
                        )
                    """))
                    await conn.execute(sqlalchemy.text("INSERT INTO country_prices_new (id, country_code, iso_code, country_name, price, buy_price, approve_delay, updated_at) SELECT coalesce(id, 0), coalesce(country_code, ''), coalesce(iso_code, 'XX'), coalesce(country_name, 'Unknown'), coalesce(price, 0), coalesce(buy_price, 0), coalesce(approve_delay, 0), updated_at FROM country_prices"))
                    await conn.execute(sqlalchemy.text("DROP TABLE country_prices"))
                    await conn.execute(sqlalchemy.text("ALTER TABLE country_prices_new RENAME TO country_prices"))
            except Exception as e:
                logger.error(f"Failed to rebuild country_prices table: {e}")

            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE country_prices ADD COLUMN updated_at DATETIME"))
            except: pass

            # One-time resolution: Fix 'XX' iso_codes for legacy data
            try:
                cursor = await conn.execute(sqlalchemy.text("SELECT id, country_code FROM country_prices WHERE iso_code = 'XX' OR iso_code IS NULL"))
                rows = cursor.fetchall()
                for row_id, c_code in rows:
                    try:
                        clean_code = c_code.strip().lstrip('+').lstrip('0')
                        numeric_code = int(clean_code)
                        detected_iso = phonenumbers.region_code_for_country_code(numeric_code)
                        if detected_iso:
                            await conn.execute(sqlalchemy.text("UPDATE country_prices SET iso_code = :iso WHERE id = :id"), {"iso": detected_iso, "id": row_id})
                    except: pass
            except: pass

            try:
                await conn.execute(sqlalchemy.text("UPDATE country_prices SET updated_at = '" + datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + "' WHERE updated_at IS NULL"))
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
    iso_code: str = "XX"
    price: float
    buy_price: float
    approve_delay: int

class UserPriceCreate(BaseModel):
    user_id: int
    country_code: str
    iso_code: str = "XX"
    buy_price: float

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
                        iso = getattr(cp, 'iso_code', None) or 'XX'
                        flag = get_flag_emoji(iso)
                except: pass
                
                countries.append({
                    "name": name,
                    "flag": flag,
                    "buy_price": price,
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

@app.get("/api/store/history")
async def get_store_history(user_id: int):
    try:
        async with async_session() as session:
            stmt = select(Account).where(Account.buyer_id == user_id).order_by(Account.id.desc())
            results = (await session.execute(stmt)).scalars().all()
            
            history = []
            for a in results:
                # Resolve flag
                flag = "🌐"
                try:
                    cp = (await session.execute(select(CountryPrice).where(CountryPrice.country_name == a.country))).scalar()
                    if cp:
                        flag = get_flag_emoji(cp.iso_code)
                except: pass
                
                history.append({
                    "phone": a.phone_number,
                    "country": a.country,
                    "flag": flag,
                    "price": a.price,
                    "date": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "N/A"
                })
            return history
    except Exception as e:
        logger.error(f"Store History Error: {e}")
        return []

@app.get("/api/admin/sourcing/data")
async def get_sourcing_data():
    try:
        async with async_session() as session:
            total_sourced = (await session.execute(select(func.count(Account.id)))).scalar() or 0
            pending_count = (await session.execute(select(func.count(Account.id)).where(Account.status == AccountStatus.PENDING))).scalar() or 0
            accepted_sourced = (await session.execute(select(func.count(Account.id)).where(Account.status.in_([AccountStatus.AVAILABLE, AccountStatus.SOLD])))).scalar() or 0
            rejected_sourced = (await session.execute(select(func.count(Account.id)).where(Account.status == AccountStatus.REJECTED))).scalar() or 0
            
            # Withdrawal stats
            withdraw_pending = (await session.execute(select(func.count(WithdrawalRequest.id)).where(WithdrawalRequest.status == WithdrawalStatus.PENDING))).scalar() or 0
            withdraw_approved = (await session.execute(select(func.count(WithdrawalRequest.id)).where(WithdrawalRequest.status == WithdrawalStatus.APPROVED))).scalar() or 0
            withdraw_rejected = (await session.execute(select(func.count(WithdrawalRequest.id)).where(WithdrawalRequest.status == WithdrawalStatus.REJECTED))).scalar() or 0
            total_paid_amount = (await session.execute(select(func.sum(WithdrawalRequest.amount)).where(WithdrawalRequest.status == WithdrawalStatus.APPROVED))).scalar() or 0
            
            recent_result = await session.execute(
                select(Account).order_by(Account.id.desc()).limit(50)
            )
            recent = []
            for a in recent_result.scalars().all():
                flag = "🌐"
                try:
                    p = phonenumbers.parse(a.phone_number)
                    flag = get_flag_emoji(phonenumbers.region_code_for_number(p))
                except: pass
                
                # Fetch actual buy_price from CountryPrice
                actual_buy_price = 0
                try:
                    parsed = phonenumbers.parse(a.phone_number)
                    cc = str(parsed.country_code)
                    target_iso = phonenumbers.region_code_for_number(parsed)
                    
                    stmt = select(CountryPrice).where(
                        CountryPrice.country_code == cc,
                        CountryPrice.iso_code == target_iso
                    )
                    cp_row = (await session.execute(stmt)).scalar()
                    if not cp_row:
                         cp_row = (await session.execute(select(CountryPrice).where(CountryPrice.country_code == cc))).scalar()
                         
                    if cp_row:
                        actual_buy_price = cp_row.buy_price
                except: pass
                
                recent.append({
                    "phone": a.phone_number,
                    "country": f"{flag} {a.country}",
                    "buy_price": actual_buy_price,
                    "status": a.status.name,
                    "seller_id": a.seller_id,
                    "date": a.created_at.strftime("%Y-%m-%d %H:%M")
                })

            prices_result = await session.execute(
                select(CountryPrice).where(CountryPrice.buy_price > 0).order_by(CountryPrice.updated_at.desc())
            )
            prices = []
            for p in prices_result.scalars().all():
                iso = getattr(p, 'iso_code', None) or 'XX'
                flag = get_flag_emoji(iso)
                prices.append({
                    "code": p.country_code, 
                    "iso": iso,
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

            user_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
            total_sourcing_balance = (await session.execute(select(func.sum(User.balance_sourcing)))).scalar() or 0.0

            users_result = await session.execute(select(User).order_by(User.id.desc()).limit(200))
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
                    "accepted_sourced": accepted_sourced,
                    "rejected_sourced": rejected_sourced,
                    "total_balance": round(total_sourcing_balance, 2),
                    "user_count": user_count,
                    "withdraw_pending": withdraw_pending,
                    "withdraw_approved": withdraw_approved,
                    "withdraw_rejected": withdraw_rejected,
                    "total_paid_amount": float(total_paid_amount)
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

            user_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
            stock_count = (await session.execute(select(func.count(Account.id)).where(Account.status == AccountStatus.AVAILABLE))).scalar() or 0
            total_balance = (await session.execute(select(func.sum(User.balance_store)))).scalar() or 0.0

            users_result = await session.execute(select(User).order_by(User.id.desc()).limit(200))
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
                select(Account)
                .where(Account.status == AccountStatus.SOLD)
                .order_by(Account.id.desc())
                .limit(50)
            )
            transactions = []
            for acc in tx_result.scalars().all():
                flag = "🌐"
                try:
                    p = phonenumbers.parse(acc.phone_number)
                    flag = get_flag_emoji(phonenumbers.region_code_for_number(p))
                except: pass
                transactions.append({
                    "buyer_id": acc.buyer_id, 
                    "price": acc.price, 
                    "phone": acc.phone_number,
                    "country": f"{flag} {acc.country}"
                })

            # Fetch all prices for store panel
            prices_result = await session.execute(
                select(CountryPrice).where(CountryPrice.price > 0).order_by(CountryPrice.updated_at.desc())
            )
            prices = []
            for p in prices_result.scalars().all():
                iso = getattr(p, 'iso_code', None) or 'XX'
                flag = get_flag_emoji(iso)
                prices.append({
                    "code": p.country_code,
                    "iso": iso,
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
                status=AccountStatus.AVAILABLE,
                created_at=datetime.now()
            )
            session.add(new_acc)
            await session.commit()
            
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Login Complete Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/sourcing/price/update")
async def update_sourcing_price(data: dict):
    # data: {country_code, buy_price, approve_delay, iso_code, country_name}
    code = data.get("country_code")
    iso = data.get("iso_code", "XX")
    buy_p = float(data.get("buy_price", 0))
    delay = int(data.get("approve_delay", 0))
    c_name = data.get("country_name")

    # If iso/name not provided, auto-detect (legacy or basic add)
    if iso == "XX" or not c_name:
        name_only, _, detected_iso = resolve_country_info(code)
        if not c_name: c_name = name_only
        if iso == "XX": iso = detected_iso

    async with async_session() as session:
        # Match by both code and ISO to support shared prefixes like +1
        stmt = select(CountryPrice).where(
            CountryPrice.country_code == code,
            CountryPrice.iso_code == iso
        )
        cp = (await session.execute(stmt)).scalar()
        
        if cp:
            cp.buy_price = buy_p
            cp.approve_delay = delay
            cp.updated_at = datetime.utcnow()
            if c_name: cp.country_name = c_name
        else:
            cp = CountryPrice(
                country_code=code,
                iso_code=iso,
                country_name=c_name, 
                price=0,
                buy_price=buy_p,
                approve_delay=delay
            )
            session.add(cp)
        await session.commit()
    return {"status": "success"}

@app.get("/api/admin/sourcing/user-prices")
async def get_user_prices():
    from database.models import UserCountryPrice, User
    async with async_session() as session:
        result = await session.execute(
            select(UserCountryPrice, User)
            .join(User, UserCountryPrice.user_id == User.id)
            .order_by(UserCountryPrice.created_at.desc())
        )
        data = []
        for ucp, user in result.all():
            flag = "🌐"
            name = f"Code {ucp.country_code}"
            
            # Use iso_code if available (not 'XX')
            iso = ucp.iso_code if ucp.iso_code and ucp.iso_code != 'XX' else None
            
            try:
                import pycountry
                if iso:
                    from web_admin import get_flag_emoji
                    flag = get_flag_emoji(iso)
                    country = pycountry.countries.get(alpha_2=iso)
                    if country:
                        name = country.name
                        import re
                        name = re.sub(r'\s*\(?[A-Z]{2,3}\)?\s*$', '', name).strip()
                else:
                    n, f, _ = resolve_country_info(ucp.country_code)
                    if n != "Unknown":
                        name = n
                        flag = f
            except: pass
            
            data.append({
                "id": ucp.id,
                "user_id": user.id,
                "user_name": user.full_name or "N/A",
                "user_handle": f"@{user.username}" if user.username else "N/A",
                "country_code": ucp.country_code,
                "iso_code": ucp.iso_code,
                "country_name": f"{flag} {name}",
                "buy_price": ucp.buy_price,
                "date": ucp.created_at.strftime("%Y-%m-%d %H:%M")
            })
        return {"prices": data}

@app.post("/api/admin/sourcing/user-prices")
async def add_user_price(data: UserPriceCreate):
    from database.models import UserCountryPrice, User
    async with async_session() as session:
        user = await session.get(User, data.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Check if exists
        stmt = select(UserCountryPrice).where(
            UserCountryPrice.user_id == data.user_id,
            UserCountryPrice.country_code == data.country_code,
            UserCountryPrice.iso_code == data.iso_code
        )
        existing = (await session.execute(stmt)).scalar()
        if existing:
            existing.buy_price = data.buy_price
        else:
            new_ucp = UserCountryPrice(
                user_id=data.user_id,
                country_code=data.country_code,
                iso_code=data.iso_code,
                buy_price=data.buy_price
            )
            session.add(new_ucp)
        await session.commit()
        return {"status": "success"}

@app.delete("/api/admin/sourcing/user-prices/{id}")
async def delete_user_price(id: int):
    from database.models import UserCountryPrice
    async with async_session() as session:
        ucp = await session.get(UserCountryPrice, id)
        if ucp:
            await session.delete(ucp)
            await session.commit()
        return {"status": "success"}

@app.delete("/api/admin/prices/delete")
async def delete_price_entry(code: str, iso: str, bot: str = "store"):
    async with async_session() as session:
        stmt = select(CountryPrice).where(
            CountryPrice.country_code == code,
            CountryPrice.iso_code == iso
        )
        cp = (await session.execute(stmt)).scalar()
        if cp:
            if bot == "sourcing":
                cp.buy_price = 0
            else:
                cp.price = 0
            
            # If both prices are 0, we can fully delete the entry
            if cp.price == 0 and cp.buy_price == 0:
                await session.delete(cp)
        
        await session.commit()
    return {"status": "success"}

@app.post("/api/admin/prices/update")
async def update_price(data: PriceUpdate):
    """General update (mostly used by Store admin now)"""
    async with async_session() as session:
        # Identify by code and ISO
        stmt = select(CountryPrice).where(
            CountryPrice.country_code == data.country_code,
            CountryPrice.iso_code == data.iso_code
        )
        cp = (await session.execute(stmt)).scalar()
        
        if cp:
            # PARTIAL UPDATE: Only touch store price and name
            cp.price = data.price
            if data.country_name and data.country_name != "Unknown":
                cp.country_name = data.country_name
            elif not cp.country_name or cp.country_name == "Unknown":
                name, _, _ = resolve_country_info(data.country_code)
                cp.country_name = name
            
            # CRITICAL: Do NOT overwrite buy_price or approve_delay if update is from store dashboard
            # We keep whatever is currently there.
            cp.updated_at = datetime.utcnow()
        else:
            name = data.country_name
            iso = data.iso_code
            if not name or name == "Unknown" or iso == "XX":
                name_det, _, iso_det = resolve_country_info(data.country_code)
                if not name or name == "Unknown": name = name_det
                if iso == "XX": iso = iso_det
                
            cp = CountryPrice(
                country_code=data.country_code,
                iso_code=iso,
                country_name=name, 
                price=data.price,
                buy_price=0, # Initial sourcing buy price is 0
                approve_delay=0
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
                # Add new user without active flags
                user = User(id=user_id, balance_sourcing=0.0, balance_store=0.0)
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
            prices_result = await session.execute(select(CountryPrice).where(CountryPrice.buy_price > 0).order_by(CountryPrice.updated_at.desc()))
            prices = prices_result.scalars().all()
            
            # Get custom user prices
            from database.models import UserCountryPrice
            custom_prices_result = await session.execute(select(UserCountryPrice).where(UserCountryPrice.user_id == user_id))
            custom_prices = {cp.country_code: cp.buy_price for cp in custom_prices_result.scalars().all()}
            
            formatted_prices = []
            seen_codes = set()
            
            # First, add global prices, applying custom overrides if they exist
            for p in prices:
                try:
                    iso = getattr(p, 'iso_code', None) or 'XX'
                    flag = get_flag_emoji(iso)
                    default_name = resolve_country_info(p.country_code)[0]
                    name = p.country_name if p.country_name and p.country_name != "Unknown" else default_name
                    
                    price_val = custom_prices.get(p.country_code, p.buy_price)
                    if price_val > 0:
                        formatted_prices.append({
                            "name": name,
                            "flag": flag,
                            "code": p.country_code,
                            "price": price_val
                        })
                        seen_codes.add(p.country_code)
                except Exception as inner_e:
                    logger.error(f"Error processing price for code {p.country_code}: {inner_e}")
                    
            # Next, add any custom prices that are NOT in the global active list
            for cc, cp_buy_price in custom_prices.items():
                if cc not in seen_codes and cp_buy_price > 0:
                    try:
                        n, f, _ = resolve_country_info(cc)
                        name = n if n != "Unknown" else f"Code {cc}"
                        formatted_prices.append({
                            "name": name,
                            "flag": f,
                            "code": cc,
                            "price": cp_buy_price
                        })
                    except: pass
                
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

        # Pre-check 2: Country availability & Pricing
        try:
            parsed = phonenumbers.parse(phone)
            cc = str(parsed.country_code)
            target_iso = phonenumbers.region_code_for_number(parsed) or 'XX'
            
            async with async_session() as session:
                from sqlalchemy import or_
                # 1. Try to find a global CountryPrice (Specific ISO or fallback XX, with or without + in code)
                cc_clean = cc.lstrip('+')
                cc_with_plus = "+" + cc_clean
                
                cp_stmt = select(CountryPrice).where(
                    or_(CountryPrice.country_code == cc_clean, CountryPrice.country_code == cc_with_plus),
                    or_(CountryPrice.iso_code == target_iso, CountryPrice.iso_code == 'XX')
                ).order_by(CountryPrice.iso_code.asc()) # Prefer specific ISO
                cp = (await session.execute(cp_stmt)).scalars().first()
                
                # 2. Check for custom user price override
                ucp_stmt = select(UserCountryPrice).where(
                    UserCountryPrice.user_id == data.user_id, 
                    or_(UserCountryPrice.country_code == cc_clean, UserCountryPrice.country_code == cc_with_plus),
                    or_(UserCountryPrice.iso_code == target_iso, UserCountryPrice.iso_code == 'XX')
                ).order_by(UserCountryPrice.iso_code.asc())
                ucp = (await session.execute(ucp_stmt)).scalars().first()
                
                # 3. Determine final buy price
                final_buy_price = ucp.buy_price if ucp else (cp.buy_price if cp else 0)
                
                if final_buy_price <= 0:
                    raise HTTPException(status_code=400, detail="Sorry, this country is not requested at the moment.")
        except HTTPException as he: raise he
        except Exception as inner_e:
            logger.error(f"Pricing Check Error: {inner_e}")
            raise HTTPException(status_code=400, detail="Invalid phone number format or country not supported.")

        phone_code_hash = await request_app_code(data.user_id, phone)
        return {"hash": phone_code_hash, "phone": phone}
    except Exception as e:
        logger.error(f"Seller OTP Request Error: {e}")
        if isinstance(e, HTTPException): raise e
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
                phone_clean = data.phone.strip()
                if not phone_clean.startswith("+"): phone_clean = "+" + phone_clean
                parsed = phonenumbers.parse(phone_clean)
                cc = str(parsed.country_code)
                target_iso = phonenumbers.region_code_for_number(parsed) or 'XX'
                
                from sqlalchemy import or_
                # 1. Global Price (Specific ISO or fallback XX, with or without + in code)
                cc_clean = cc.lstrip('+')
                cc_with_plus = "+" + cc_clean
                
                cp_stmt = select(CountryPrice).where(
                    or_(CountryPrice.country_code == cc_clean, CountryPrice.country_code == cc_with_plus),
                    or_(CountryPrice.iso_code == target_iso, CountryPrice.iso_code == 'XX')
                ).order_by(CountryPrice.iso_code.asc()) # Prefer specific ISO
                cp = (await session.execute(cp_stmt)).scalars().first()
                
                # 2. Custom User Price
                ucp_stmt = select(UserCountryPrice).where(
                    UserCountryPrice.user_id == data.user_id, 
                    or_(UserCountryPrice.country_code == cc_clean, UserCountryPrice.country_code == cc_with_plus),
                    or_(UserCountryPrice.iso_code == target_iso, UserCountryPrice.iso_code == 'XX')
                ).order_by(UserCountryPrice.iso_code.asc())
                ucp = (await session.execute(ucp_stmt)).scalars().first()
                
                # 3. Final Price
                price = ucp.buy_price if ucp else (cp.buy_price if cp else 0)
            except Exception as inner_e:
                logger.error(f"Submit OTP Pricing Error: {inner_e}")

            new_acc = Account(
                phone_number=data.phone,
                country=data.country,
                price=price,
                session_string=session_string,
                status=AccountStatus.PENDING,
                seller_id=data.user_id,
                created_at=datetime.now()
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
        if not user:
            raise HTTPException(status_code=403, detail="User not verified for sourcing bot.")
        
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
async def get_withdrawals(user_id: int, page: int = 1, status: str = "all"):
    page_size = 10
    offset = (page - 1) * page_size
    async with async_session() as session:
        # Build base filter
        base_filters = [WithdrawalRequest.user_id == user_id]
        if status != "all":
            try:
                # Convert string status to enum
                enum_status = WithdrawalStatus(status.upper())
                base_filters.append(WithdrawalRequest.status == enum_status)
            except: pass

        # Get total count for pagination
        count_stmt = select(func.count(WithdrawalRequest.id)).where(*base_filters)
        total_count = (await session.execute(count_stmt)).scalar() or 0
        total_pages = (total_count + page_size - 1) // page_size

        # Get page data
        stmt = select(WithdrawalRequest).where(*base_filters).order_by(WithdrawalRequest.created_at.desc()).offset(offset).limit(page_size)
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
                "date": r.created_at.strftime("%Y-%m-%d %H:%M")
            })
        return {
            "history": history,
            "total_pages": total_pages,
            "current_page": page,
            "total_count": total_count
        }

@app.get("/api/admin/withdrawals/all")
async def admin_get_all_withdrawals(page: int = 1, status: str = "all"):
    page_size = 10
    offset = (page - 1) * page_size
    async with async_session() as session:
        # Build base filter
        filters = []
        if status != "all":
            # Map string to Enum member safely
            s_map = {
                "pending": WithdrawalStatus.PENDING, 
                "approved": WithdrawalStatus.APPROVED, 
                "rejected": WithdrawalStatus.REJECTED
            }
            if status.lower() in s_map:
                filters.append(WithdrawalRequest.status == s_map[status.lower()])
            
        # Count total
        count_stmt = select(func.count(WithdrawalRequest.id)).where(*filters)
        total_count = (await session.execute(count_stmt)).scalar() or 0
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
        
        # Build results query
        stmt = select(WithdrawalRequest).where(*filters).order_by(WithdrawalRequest.created_at.desc()).offset(offset).limit(page_size)
        results = (await session.execute(stmt)).scalars().all()
        
        history = []
        for r in results:
            # Fetch user info for display
            u = await session.get(User, r.user_id)
            history.append({
                "id": r.id,
                "user_id": r.user_id,
                "user_name": u.full_name if u else "N/A",
                "user_handle": f"@{u.username}" if u and u.username else "N/A",
                "transaction_id": r.transaction_id,
                "amount": r.amount,
                "method": r.method,
                "address": r.address,
                "status": r.status.value,
                "date": r.created_at.strftime("%Y-%m-%d %H:%M")
            })
            
        return {
            "history": history,
            "total_pages": total_pages,
            "current_page": page,
            "total_count": total_count
        }

@app.post("/api/admin/withdrawals/action")
async def admin_withdrawal_action(data: WithdrawAction):
    async with async_session() as session:
        req = await session.get(WithdrawalRequest, data.request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
            
        if req.status != WithdrawalStatus.PENDING:
            raise HTTPException(status_code=400, detail=f"Request is already {req.status.value}")
            
        # 1. Update Status
        if data.action == "approve":
            req.status = WithdrawalStatus.APPROVED
            btn_text = "✅ Approved"
            msg_theme = "🟢"
        elif data.action == "reject":
            # NO REFUND as per user request
            req.status = WithdrawalStatus.REJECTED
            btn_text = "❌ Rejected (No Refund)"
            msg_theme = "🔴"
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
            
        await session.commit()
        
        # 2. Notify User via Bot
        bot = getattr(app.state, 'bot_seller', None)
        if bot:
            try:
                # Localized message based on user preference
                user = await session.get(User, req.user_id)
                lang = user.language if user else "ar"
                
                if lang == "ar":
                    msg = (
                        f"📢 **تنبيه سحب جديد**\n\n"
                        f"الحالة: {msg_theme} {data.action.upper()}\n"
                        f"المبلغ: ${req.amount:.2f}\n"
                        f"المعرف: <code>{req.transaction_id}</code>\n\n"
                        f"{'✅ تم تحويل أموالك بنجاح.' if data.action == 'approve' else '❌ تم رفض طلب السحب الخاص بك.'}"
                    )
                else:
                    msg = (
                        f"📢 **Withdrawal Update**\n\n"
                        f"Status: {msg_theme} {data.action.upper()}\n"
                        f"Amount: ${req.amount:.2f}\n"
                        f"ID: <code>{req.transaction_id}</code>\n\n"
                        f"{'✅ Your funds have been transferred successfully.' if data.action == 'approve' else '❌ Your withdrawal request has been rejected.'}"
                    )
                
                await bot.send_message(req.user_id, msg, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Failed to send withdrawal notification: {e}")
                
        return {"ok": True, "status": "success", "message": f"Withdrawal {data.action}ed successfully"}


@app.get("/api/admin/countries-for-code/{code}")
async def get_countries_for_code(code: str):
    """Returns a list of matching countries for a given numeric code."""
    try:
        clean_code = code.strip().lstrip('+').lstrip('0')
        numeric_code = int(clean_code)
        regions = phonenumbers.COUNTRY_CODE_TO_REGION_CODE.get(numeric_code, [])
        
        results = []
        for r in regions:
            try:
                country = pycountry.countries.get(alpha_2=r)
                if country:
                    name = country.name
                    name = re.sub(r'\s*\(?[A-Z]{2,3}\)?\s*$', '', name).strip()
                    results.append({"iso": r, "name": name, "flag": get_flag_emoji(r)})
            except: pass
        return results
    except:
        return []

@app.get("/api/seller/detect-country")
async def detect_country(phone: str):
    try:
        parsed = phonenumbers.parse(phone if phone.startswith('+') else f"+{phone}")
        country_code = str(parsed.country_code)
        target_iso = phonenumbers.region_code_for_number(parsed) or 'XX'
        
        async with async_session() as session:
            # Enforce exact match for ISO code (crucial for shared codes like +1, +7)
            stmt = select(CountryPrice).where(
                CountryPrice.country_code == country_code,
                CountryPrice.iso_code == target_iso
            )
            cp = (await session.execute(stmt)).scalar()
            
            # Ensure the country actually has an active buying price
            if cp and cp.buy_price > 0:
                return {
                    "found": True,
                    "name": cp.country_name,
                    "flag": get_flag_emoji(target_iso) if target_iso != 'XX' else "🌐",
                    "price": cp.buy_price
                }
    except Exception as e:
        logger.error(f"Detection Error: {e}")
    return {"found": False}

@app.get("/api/seller/accounts")
async def get_seller_accounts(user_id: int, page: int = 1, limit: int = 10):
    async with async_session() as session:
        offset = (page - 1) * limit
        
        # Get total count for pagination
        total_count = (await session.execute(
            select(func.count(Account.id)).where(Account.seller_id == user_id)
        )).scalar() or 0
        total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
        
        stmt = select(Account).where(Account.seller_id == user_id).order_by(Account.created_at.desc()).offset(offset).limit(limit)
        results = (await session.execute(stmt)).scalars().all()
        accounts_data = []
        for a in results:
            # Detect reward price for seller
            actual_buy_price = 0
            approve_delay = 0
            flag = "🌐"
            try:
                parsed = phonenumbers.parse(a.phone_number)
                cc = str(parsed.country_code)
                region = phonenumbers.region_code_for_number(parsed)
                flag = get_flag_emoji(region)
                cp_row = (await session.execute(select(CountryPrice).where(CountryPrice.country_code == cc))).scalar()
                if cp_row:
                    actual_buy_price = cp_row.buy_price
                    approve_delay = cp_row.approve_delay
            except: pass

            ready_at = (a.created_at + timedelta(seconds=approve_delay)) if a.created_at else None

            accounts_data.append({
                "phone": a.phone_number,
                "status": a.status.name,
                "country": f"{flag} {a.country}",
                "buy_price": actual_buy_price,
                "ready_at": int(ready_at.timestamp() * 1000) if ready_at else None,
                "date": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "N/A"
            })

        return {
            "accounts": accounts_data,
            "total_pages": total_pages,
            "current_page": page
        }

@app.get("/api/admin/sourcing/history")
async def get_admin_sourcing_history(page: int = 1, limit: int = 10):
    async with async_session() as session:
        offset = (page - 1) * limit
        
        total_count = (await session.execute(
            select(func.count(Account.id))
        )).scalar() or 0
        total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
        
        stmt = select(Account).order_by(Account.id.desc()).offset(offset).limit(limit)
        results = (await session.execute(stmt)).scalars().all()
        
        history = []
        for a in results:
            flag = "🌐"
            approve_delay = 0
            price = 0
            try:
                parsed = phonenumbers.parse(a.phone_number)
                cc = str(parsed.country_code)
                region = phonenumbers.region_code_for_number(parsed)
                flag = get_flag_emoji(region)
                cp_row = (await session.execute(select(CountryPrice).where(CountryPrice.country_code == cc))).scalar()
                if cp_row:
                    price = cp_row.buy_price
                    approve_delay = cp_row.approve_delay
            except: pass

            ready_at = (a.created_at + timedelta(seconds=approve_delay)) if a.created_at else None

            history.append({
                "id": a.id,
                "phone": a.phone_number,
                "country": f"{flag} {a.country}",
                "buy_price": price,
                "status": a.status.name,
                "seller_id": a.seller_id,
                "ready_at": int(ready_at.timestamp() * 1000) if ready_at else None,
                "date": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "N/A"
            })
            
        return {
            "history": history,
            "total_pages": total_pages,
            "current_page": page
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
