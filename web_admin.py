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
from sqlalchemy import select, delete, update, func, text, or_, cast, String
from database.engine import async_session
from database.models import User, Account, Transaction, AccountStatus, TransactionType, CountryPrice, WithdrawalRequest, WithdrawalStatus, UserCountryPrice, Deposit, AppSetting, UserStorePrice, ApiServer
import re
import pycountry
import hmac
import hashlib
import time
import requests
from pydantic import BaseModel
from typing import List
# Delayed imports inside functions to avoid pyrogram event loop issues
from services.external_provider import ExternalProvider
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

class DepositSubmit(BaseModel):
    user_id: int
    txid: str
    method: str = "Binance Pay"

class StoreSettingsSubmit(BaseModel):
    binance_api_key: str
    binance_api_secret: str
    binance_pay_id: str
    trx_address: str
    usdt_bep20_address: str

class ApiServerSubmit(BaseModel):
    id: int | None = None
    name: str
    url: str
    api_key: str
    server_type: str = "standard"
    extra_id: str | None = None
    profit_margin: float
    is_active: bool

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
    """Resolve ISO code and Country Name. Handles numeric codes, Alpha-2, and Alpha-3."""
    import pycountry
    import phonenumbers
    import re
    try:
        code_str = str(country_code_str).strip().upper().lstrip('+')
        if not code_str: return "Unknown", "🌐", "XX"

        # 1. Handle if it's already an ISO code (Alpha-2 or Alpha-3)
        if not code_str.isdigit() and len(code_str) in [2, 3]:
            try:
                country = None
                if len(code_str) == 2:
                    country = pycountry.countries.get(alpha_2=code_str)
                else:
                    country = pycountry.countries.get(alpha_3=code_str)
                
                if country:
                    name = re.sub(r'\s*\(?[A-Z]{2,3}\)?\s*$', '', country.name).strip()
                    iso = country.alpha_2
                    return name, get_flag_emoji(iso), iso
            except: pass

        # 2. Handle if full_phone is provided
        if full_phone:
            try:
                parsed = phonenumbers.parse(full_phone if full_phone.startswith('+') else f"+{full_phone}")
                iso_code = phonenumbers.region_code_for_number(parsed)
                country = pycountry.countries.get(alpha_2=iso_code)
                name = country.name if country else iso_code
                name = re.sub(r'\s*\(?[A-Z]{2,3}\)?\s*$', '', name).strip()
                return name, get_flag_emoji(iso_code), iso_code
            except: pass

        # 3. Handle numeric calling code prefix
        if code_str.isdigit():
            try:
                numeric_code = int(code_str)
                iso_code = phonenumbers.region_code_for_country_code(numeric_code)
                flag = get_flag_emoji(iso_code)
                
                name = f"Country {numeric_code}"
                country = pycountry.countries.get(alpha_2=iso_code)
                if country:
                    name = re.sub(r'\s*\(?[A-Z]{2,3}\)?\s*$', '', country.name).strip()
                return name, flag, iso_code
            except: pass
        
        return f"Code {code_str}", "🌐", "XX"
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
            # Add approve_delay to user_country_prices if missing
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE user_country_prices ADD COLUMN approve_delay INTEGER DEFAULT 0"))
            except: pass
            
            # Add otp_code to accounts if missing
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE accounts ADD COLUMN otp_code VARCHAR"))
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
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE accounts ADD COLUMN purchased_at DATETIME"))
            except: pass
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE accounts ADD COLUMN server_id INTEGER"))
            except: pass
            try:
                await conn.execute(sqlalchemy.text("ALTER TABLE accounts ADD COLUMN hash_code TEXT"))
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

            # Fix: Sync existing available accounts with CountryPrice selling prices
            try:
                await conn.execute(sqlalchemy.text("""
                    UPDATE accounts 
                    SET price = (
                        SELECT price FROM country_prices 
                        WHERE country_prices.country_name = accounts.country 
                        LIMIT 1
                    )
                    WHERE status = 'available' 
                    AND EXISTS (
                        SELECT 1 FROM country_prices WHERE country_prices.country_name = accounts.country
                    )
                """))
                logger.info("Successfully synced available account prices with CountryPrice table.")
            except Exception as e:
                logger.warning(f"Failed to sync account prices: {e}")

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
    id: int | None = None
    user_id: int
    country_code: str
    iso_code: str = "XX"
    buy_price: float
    approve_delay: int = 0

class UserStorePriceCreate(BaseModel):
    id: int | None = None
    user_id: int
    country_code: str
    iso_code: str = "XX"
    sell_price: float

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
            # 1. Local Stock
            stmt = select(Account.country, func.count(Account.id).label('cnt')).where(
                Account.status == AccountStatus.AVAILABLE,
                Account.server_id == None
            ).group_by(Account.country)
            
            local_results = (await session.execute(stmt)).all()
            logger.info(f"Local results: {len(local_results)} countries")
            
            countries_map = {}
            for row in local_results:
                name, count = row
                countries_map[name] = {"name": name, "count": count, "server_id": None}

            # 2. External Stock
            active_servers = (await session.execute(select(ApiServer).where(ApiServer.is_active == True))).scalars().all()
            logger.info(f"Active external servers: {len(active_servers)}")
            for srv in active_servers:
                try:
                    logger.info(f"Processing server: {srv.name} ({srv.url})")
                    provider = ExternalProvider(
                        srv.name, srv.url, srv.api_key, srv.profit_margin,
                        server_type=getattr(srv, 'server_type', 'standard'),
                        extra_id=getattr(srv, 'extra_id', None)
                    )
                    srv_countries = await provider.get_countries()
                    
                    if not srv_countries:
                        logger.warning(f"Server {srv.name} returned no data.")
                        continue

                    # Handle common error formats in responses
                    if isinstance(srv_countries, dict) and srv_countries.get("status") in ["error", "fail"]:
                        logger.error(f"Server {srv.name} API Error: {srv_countries.get('message')}")
                        continue

                    # Normalize srv_countries to a list of dicts
                    countries_list = []
                    
                    # 1. Super Parser: Find the node that actually contains country data
                    def find_country_node(node):
                        if isinstance(node, dict):
                            # Case A: Dict with country keys (EG, PS, etc.)
                            if any(k in node for k in ["EG", "PS", "SA", "US", "20", "966", "970"]):
                                return node
                            # Case B: Dict that contains common keys like price/count
                            if any(k in node for k in ["price", "count", "rate", "cost", "stock"]):
                                return node
                            
                            # Otherwise, drill down
                            for k, v in node.items():
                                res = find_country_node(v)
                                if res: return res
                        elif isinstance(node, list):
                            # Case C: List of objects - check first few items
                            for item in node[:3]:
                                if isinstance(item, dict):
                                    if any(k in item for k in ["price", "count", "rate", "cost", "stock"]):
                                        return node # Return the whole list
                                    res = find_country_node(item)
                                    if res: return node # Return the whole list if children are good
                        return None

                    # Special handling for Spider Service typo-prone and split structure
                    # result: { countries: {1: {ISO: price}}, cuantity: {1: {ISO: count}} }
                    spider_prices = {}
                    spider_counts = {}
                    
                    if isinstance(srv_countries, dict) and "result" in srv_countries:
                        res = srv_countries["result"]
                        if isinstance(res, dict):
                            # Try to find prices
                            p_node = res.get("countries")
                            if isinstance(p_node, dict) and "1" in p_node: p_node = p_node["1"]
                            if isinstance(p_node, dict): spider_prices = p_node
                            
                            # Try to find quantities (handling the 'cuantity' typo)
                            q_node = res.get("cuantity") or res.get("quantity")
                            if isinstance(q_node, dict) and "1" in q_node: q_node = q_node["1"]
                            if isinstance(q_node, dict): spider_counts = q_node

                    if spider_prices:
                        # If we found Spider-specific split data, merge it
                        for code, price in spider_prices.items():
                            try:
                                countries_list.append({
                                    "country": code,
                                    "price": float(price),
                                    "count": int(spider_counts.get(code, 999))
                                })
                            except: continue
                    else:
                        # Fallback to Super Parser for TG-Lion and others
                        data_node = find_country_node(srv_countries)
                        if not data_node:
                            data_node = srv_countries
                            for key in ["result", "data", "countries_info", "countries"]:
                                if isinstance(data_node, dict) and key in data_node:
                                    data_node = data_node[key]
                                    break
                        
                        if isinstance(data_node, dict):
                            for code, val in data_node.items():
                                if code.lower() in ["status", "message", "error", "ok", "msg", "currency", "success"]: continue
                                if isinstance(val, dict):
                                    entry = val.copy()
                                    entry["country"] = code
                                    countries_list.append(entry)
                                elif isinstance(val, (int, float, str)):
                                    try:
                                        price_val = float(val)
                                        countries_list.append({
                                            "country": code,
                                            "count": 999,
                                            "price": price_val
                                        })
                                    except: continue
                        elif isinstance(data_node, list):
                            # Normalize list items to have 'country' key
                            for item in data_node:
                                if not isinstance(item, dict): continue
                                normalized = item.copy()
                                if "country" not in normalized:
                                    # Try to find country code in common keys
                                    for k in ["id", "iso", "code", "name"]:
                                        if k in normalized:
                                            normalized["country"] = normalized[k]
                                            break
                                countries_list.append(normalized)
                    
                    for c in countries_list:
                        raw_name = c.get("name") or c.get("country") or c.get("country_name") or c.get("country_code")
                        if not raw_name: continue
                        
                        # Use 'code' field (ISO Alpha-2) if available for accurate resolution
                        iso_from_data = c.get("code") or c.get("iso") or c.get("country_code")
                        if iso_from_data and len(str(iso_from_data).strip()) == 2:
                            resolved_name, resolved_flag, resolved_iso = resolve_country_info(str(iso_from_data).strip())
                        else:
                            resolved_name, resolved_flag, resolved_iso = resolve_country_info(str(raw_name))
                        
                        # Use resolved name if good, otherwise use raw name but clean emoji flags
                        if resolved_name and "Code " not in resolved_name:
                            name = resolved_name
                        else:
                            # Clean emoji flags from raw name to avoid duplication
                            import re as _re
                            name = _re.sub(r'[\U0001F1E0-\U0001F1FF]{2}', '', str(raw_name)).strip()
                            if not name: name = str(raw_name)
                        
                        try:
                            # Support all common quantity field names: count, qty, stock, quantity
                            count = int(c.get("count", c.get("qty", c.get("stock", c.get("quantity", 0)))))
                            p_price = float(c.get("price", c.get("rate", c.get("cost", 0))))
                            if count <= 0: continue
                            
                            if name not in countries_map:
                                countries_map[name] = {
                                    "name": name,
                                    "flag": resolved_flag,
                                    "iso": resolved_iso,
                                    "count": count,
                                    "server_id": srv.id,
                                    "p_price": p_price,
                                    "calc_price": provider.calculate_price(p_price)
                                }
                            else:
                                countries_map[name]["count"] += count
                        except Exception as parse_err:
                            logger.warning(f"[{srv.name}] Failed to parse entry: {c} — {parse_err}")
                            continue

                except Exception as srv_err:
                    logger.error(f"Error processing server {srv.name}: {srv_err}")
                    continue

            # 3. Final Assembly with Metadata & Pricing
            countries = []
            
            # Pre-fetch all pricing data to avoid N+1 queries
            all_cp = (await session.execute(select(CountryPrice))).scalars().all()
            cp_map = {cp.country_name: cp for cp in all_cp}
            
            all_usp = []
            if user_id:
                all_usp = (await session.execute(select(UserStorePrice).where(UserStorePrice.user_id == user_id))).scalars().all()
            usp_map = {usp.country_code: usp for usp in all_usp}

            for name, c_data in countries_map.items():
                flag = "🌐"
                price = 1.0
                
                cp = cp_map.get(name)
                if cp:
                    flag = get_flag_emoji(cp.iso_code)
                    price = cp.price
                elif "flag" in c_data:
                    # Use resolved flag from external if no local override
                    flag = c_data["flag"]
                
                # If external and no local price set, use calculated price
                if not cp and "calc_price" in c_data:
                    price = c_data["calc_price"]

                # Override with user-specific price if exists
                if user_id:
                    # Check both code and +code
                    cc_clean = str(c_data.get("country", "")).lstrip('+')
                    cc_plus = f"+{cc_clean}"
                    usp = usp_map.get(cc_clean) or usp_map.get(cc_plus)
                    if usp:
                        price = usp.sell_price

                countries.append({
                    "name": name,
                    "flag": flag,
                    "buy_price": price,
                    "count": c_data["count"]
                })
            
            countries.sort(key=lambda x: x["name"])
            
            # User balance & Stats
            balance = 0.0
            total_orders = 0
            total_spent = 0.0
            total_deposits = 0
            completed_orders = 0
            active_orders = 0
            unique_countries = 0
            if user_id:
                user = await session.get(User, user_id)
                if user:
                    balance = user.balance_store
                    total_orders = (await session.execute(select(func.count(Account.id)).where(Account.buyer_id == user_id))).scalar() or 0
                    
                    spent_val = (await session.execute(
                        select(func.sum(Transaction.amount)).where(
                            Transaction.user_id == user_id,
                            Transaction.type == TransactionType.BUY
                        )
                    )).scalar() or 0.0
                    total_spent = abs(float(spent_val))

                    # Personalized stats
                    total_deposits = (await session.execute(select(func.count(Deposit.id)).where(Deposit.user_id == user_id))).scalar() or 0
                    completed_orders = (await session.execute(
                        select(func.count(Account.id)).where(Account.buyer_id == user_id, Account.otp_code != None)
                    )).scalar() or 0
                    active_orders = (await session.execute(
                        select(func.count(Account.id)).where(Account.buyer_id == user_id, Account.otp_code == None)
                    )).scalar() or 0
                    unique_countries = (await session.execute(
                        select(func.count(func.distinct(Account.country))).where(Account.buyer_id == user_id)
                    )).scalar() or 0

            # Calculate Stats
            total_numbers = sum(c['count'] for c in countries)
            countries_count = len(set(c['name'] for c in countries))
            lowest_price = min((c['buy_price'] for c in countries), default=0.0)

            # Fetch bot name
            bot_name = "Numbers Store"
            try:
                from config import BOT_TOKEN
                import urllib.request
                import json
                def fetch_name():
                    try:
                        req = urllib.request.Request(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe")
                        with urllib.request.urlopen(req, timeout=2) as r:
                            res_data = json.loads(r.read().decode())
                            if res_data.get("ok"):
                                return res_data["result"].get("first_name", "Numbers Store")
                    except: return "Numbers Store"
                bot_name = await asyncio.to_thread(fetch_name)
            except: pass

            # Fetch Deposit Addresses
            from config import DEPOSIT_ADDRESS
            addr_keys = ["BINANCE_PAY_ID", "TRX_ADDRESS", "USDT_BEP20_ADDRESS"]
            addr_settings = {}
            for k in addr_keys:
                obj = (await session.execute(select(AppSetting).where(AppSetting.key == k))).scalar_one_or_none()
                addr_settings[k] = obj.value if obj and obj.value else ""

            final_binance_pay = addr_settings.get("BINANCE_PAY_ID") or DEPOSIT_ADDRESS
            final_trx = addr_settings.get("TRX_ADDRESS") or ""
            final_usdt_bep20 = addr_settings.get("USDT_BEP20_ADDRESS") or ""

        return {
            "bot_name": bot_name,
            "countries": countries,
            "user": {
                "balance": balance,
                "total_orders": total_orders,
                "total_spent": total_spent,
                "total_deposits": total_deposits,
                "completed_orders": completed_orders,
                "active_orders": active_orders,
                "unique_countries": unique_countries
            },
            "stats": {
                "total_numbers": total_numbers,
                "countries_count": countries_count,
                "lowest_price": lowest_price
            },
            "deposit_methods": {
                "binance_pay": final_binance_pay,
                "trx_trc20": final_trx,
                "usdt_bep20": final_usdt_bep20
            }
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
            
            # 1. Local Stock Check
            stmt = select(Account).where(
                Account.country == data.country, 
                Account.status == AccountStatus.AVAILABLE,
                Account.server_id == None
            ).limit(1)
            account = (await session.execute(stmt)).scalar_one_or_none()
            
            cp = (await session.execute(select(CountryPrice).where(CountryPrice.country_name == data.country))).scalar()
            final_price = cp.price if cp else 1.0

            target_srv = None
            external_country_code = None
            
            if not account:
                # 2. Try External Servers
                active_servers = (await session.execute(select(ApiServer).where(ApiServer.is_active == True))).scalars().all()
                for srv in active_servers:
                    provider = ExternalProvider(
                        srv.name, srv.url, srv.api_key, srv.profit_margin,
                        server_type=getattr(srv, 'server_type', 'standard'),
                        extra_id=getattr(srv, 'extra_id', None)
                    )
                    srv_countries = await provider.get_countries()
                    if isinstance(srv_countries, list):
                        match = next((c for c in srv_countries if (c.get("name") == data.country or c.get("country") == data.country) and int(c.get("count", 0)) > 0), None)
                        if match:
                            target_srv = srv
                            external_country_code = match.get("country")
                            if not cp: # Use calculated price if no admin price set
                                final_price = provider.calculate_price(match.get("price", 0))
                            break
                
                if not target_srv:
                    raise HTTPException(status_code=400, detail="عذراً، نفدت الأرقام!")

            # 3. Handle Personalized Pricing
            if cp:
                from database.models import UserStorePrice
                from sqlalchemy import or_
                cc_clean = cp.country_code.strip().replace('+', '')
                cc_plus = f"+{cc_clean}"
                usp = (await session.execute(
                    select(UserStorePrice).where(
                        UserStorePrice.user_id == data.user_id,
                        or_(UserStorePrice.country_code == cc_clean, UserStorePrice.country_code == cc_plus)
                    )
                )).scalar()
                if usp:
                    final_price = usp.sell_price
            
            if user.balance_store < final_price:
                raise HTTPException(status_code=400, detail="رصيدك غير كافٍ")

            if account:
                # Local Purchase Execution
                user.balance_store -= final_price
                account.status = AccountStatus.SOLD
                account.buyer_id = user.id
                account.otp_code = None
                account.purchased_at = datetime.utcnow()
                account.price = final_price
                txn = Transaction(user_id=user.id, type=TransactionType.BUY, amount=-final_price)
                session.add(txn)
                await session.commit()
                return {"status": "success", "phone": account.phone_number, "id": account.id}
            else:
                # External Purchase Execution
                provider = ExternalProvider(
                    target_srv.name, target_srv.url, target_srv.api_key, target_srv.profit_margin,
                    server_type=getattr(target_srv, 'server_type', 'standard'),
                    extra_id=getattr(target_srv, 'extra_id', None)
                )
                buy_res = await provider.buy_number(external_country_code)
                if buy_res.get("status") == "success":
                    user.balance_store -= final_price
                    new_acc = Account(
                        phone_number=buy_res.get("number"),
                        country=data.country,
                        status=AccountStatus.SOLD,
                        price=final_price,
                        buyer_id=user.id,
                        purchased_at=datetime.utcnow(),
                        server_id=target_srv.id,
                        hash_code=buy_res.get("hash_code")
                    )
                    session.add(new_acc)
                    txn = Transaction(user_id=user.id, type=TransactionType.BUY, amount=-final_price)
                    session.add(txn)
                    await session.commit()
                    return {"status": "success", "phone": new_acc.phone_number, "id": new_acc.id}
                else:
                    msg = buy_res.get("message") or "خطأ في مزود الأرقام"
                    raise HTTPException(status_code=400, detail=msg)
    except HTTPException as e: raise e
    except Exception as e:
        logger.error(f"Store Buy Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/system/purge-sold")
async def purge_sold_accounts(key: str):
    if key != "purge_key_88":
        return {"status": "error", "message": "Access denied"}
    try:
        async with async_session() as session:
            # Reset SOLD accounts back to AVAILABLE instead of deleting
            stmt = update(Account).where(Account.status == AccountStatus.SOLD).values(
                status=AccountStatus.AVAILABLE,
                buyer_id=None
            )
            await session.execute(stmt)
            await session.commit()
        return {"status": "success", "message": "Sold accounts have been purged from the system"}
    except Exception as e:
        logger.error(f"System Purge Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/store/get-code")
async def store_get_code(user_id: int, phone: str):
    from services.session_manager import get_telegram_login_code
    try:
        async with async_session() as session:
            stmt = select(Account).where(Account.phone_number == phone, Account.buyer_id == user_id)
            account = (await session.execute(stmt)).scalar_one_or_none()
            if not account: raise HTTPException(status_code=404, detail="Account not found")
            
            if account.server_id:
                # 1. Fetch from external server
                srv = await session.get(ApiServer, account.server_id)
                if not srv: raise HTTPException(status_code=500, detail="Server config missing")
                provider = ExternalProvider(
                    srv.name, srv.url, srv.api_key, srv.profit_margin,
                    server_type=getattr(srv, 'server_type', 'standard'),
                    extra_id=getattr(srv, 'extra_id', None)
                )
                code_res = await provider.get_code(account.hash_code, number=account.phone_number)
                if code_res.get("status") == "success":
                    code = code_res.get("code")
                    account.otp_code = code
                    await session.commit()
                    return {"status": "success", "code": code}
                return {"status": "pending", "message": code_res.get("message", "بانتظار وصول الكود...")}
            else:
                # 2. Local session logic
                code = await get_telegram_login_code(
                    account.session_string, 
                    after_ts=account.purchased_at.timestamp() if account.purchased_at else None
                )
                if code:
                    account.otp_code = code
                    await session.commit()
                    return {"status": "success", "code": code}
                return {"status": "pending", "message": "Code not found yet"}
    except Exception as e:
        logger.error(f"Get Code Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/store/history")
async def get_store_history(user_id: int, page: int = 1, limit: int = 10):
    try:
        async with async_session() as session:
            # Count total
            total_count = (await session.execute(
                select(func.count(Account.id)).where(Account.buyer_id == user_id)
            )).scalar() or 0
            
            total_pages = (total_count + limit - 1) // limit
            
            stmt = select(Account).where(Account.buyer_id == user_id).order_by(Account.id.desc()).offset((page - 1) * limit).limit(limit)
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
                    "date": a.purchased_at.isoformat() if a.purchased_at else (a.created_at.isoformat() if a.created_at else None),
                    "otp_code": a.otp_code
                })
            return {
                "orders": history,
                "total_pages": total_pages,
                "current_page": page,
                "total_count": total_count
            }
    except Exception as e:
        logger.error(f"Store History Error: {e}")
        return {"orders": [], "total_pages": 0, "current_page": 1, "total_count": 0}

@app.get("/api/store/deposits")
async def get_deposit_history(user_id: int, page: int = 1, limit: int = 10):
    try:
        async with async_session() as session:
            total_count = (await session.execute(
                select(func.count(Deposit.id)).where(Deposit.user_id == user_id)
            )).scalar() or 0
            
            total_pages = (total_count + limit - 1) // limit
            
            stmt = select(Deposit).where(Deposit.user_id == user_id).order_by(Deposit.id.desc()).offset((page - 1) * limit).limit(limit)
            results = (await session.execute(stmt)).scalars().all()
            
            deposits = []
            for d in results:
                deposits.append({
                    "txid": d.txid,
                    "amount": d.amount,
                    "method": d.method or "Binance Pay",
                    "date": d.created_at.isoformat() if d.created_at else None
                })
            return {
                "deposits": deposits,
                "total_pages": total_pages,
                "current_page": page,
                "total_count": total_count
            }
    except Exception as e:
        logger.error(f"Deposit History Error: {e}")
        return {"deposits": [], "total_pages": 0, "current_page": 1, "total_count": 0}

async def get_binance_price(coin: str):
    """Fetch current price of a coin in USDT."""
    if coin.upper() == "USDT":
        return 1.0
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={coin.upper()}USDT"
        response = await asyncio.to_thread(requests.get, url, timeout=5)
        if response.status_code == 200:
            return float(response.json().get("price", 0))
    except:
        pass
    return 0

async def check_binance_deposit(txid: str, api_key: str, api_secret: str):
    if not api_key or not api_secret:
        return False, "Binance API keys not configured", 0
        
    api_key = api_key.strip()
    api_secret = api_secret.strip()
    
    if "*" in api_secret or "Already Set" in api_secret:
        return False, "Invalid API Secret format in database.", 0
        
    base_url = "https://api.binance.com"
    
    # Sync time with Binance Server to avoid clock drift issues
    try:
        time_res = await asyncio.to_thread(requests.get, f"{base_url}/api/v3/time", timeout=5)
        server_time = time_res.json().get("serverTime")
        timestamp = server_time if server_time else int(time.time() * 1000)
    except:
        timestamp = int(time.time() * 1000)

    endpoint = "/sapi/v1/capital/deposit/hisrec"
    
    params = {
        "txId": txid.strip(),
        "recvWindow": 60000,
        "timestamp": timestamp
    }
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    
    signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    headers = {"X-MBX-APIKEY": api_key}
    url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
    
    try:
        response = await asyncio.to_thread(requests.get, url, headers=headers)
        data = response.json()
        if response.status_code == 200:
            if isinstance(data, list) and len(data) > 0:
                for record in data:
                    if record.get("txId") == txid:
                        status = record.get("status")
                        coin = record.get("coin", "USDT")
                        amount = float(record.get("amount", 0))
                        
                        if status == 1: # Success
                            # SECURITY: Check if transaction is too old (e.g., older than 24 hours)
                            # Binance 'insertTime' or 'updatedTime' is in ms
                            tx_time_ms = record.get("insertTime") or record.get("updatedTime") or 0
                            current_time_ms = int(time.time() * 1000)
                            
                            # 24 hours in milliseconds = 24 * 60 * 60 * 1000
                            if tx_time_ms > 0 and (current_time_ms - tx_time_ms) > (24 * 60 * 60 * 1000):
                                return False, "Transaction is too old. Only deposits from the last 24 hours are accepted.", 0

                            # Conversion Logic
                            if coin.upper() != "USDT":
                                price = await get_binance_price(coin)
                                if price <= 0:
                                    return False, f"Could not determine price for {coin}. Please contact admin.", 0
                                final_usd_amount = amount * price
                                return True, f"Success: {amount} {coin} converted to ${final_usd_amount:.2f}", final_usd_amount
                            else:
                                return True, "Success", amount
                        else:
                            return False, f"Deposit pending (status: {status}). Please wait.", 0
                return False, "Transaction ID not found in your Binance account.", 0
            else:
                return False, "Transaction ID not found or unexpected response format.", 0
        else:
            return False, f"Binance error: {data.get('msg', 'Unknown')}", 0
    except Exception as e:
        return False, f"Request error: {str(e)}", 0

@app.post("/api/store/deposit/verify")
async def store_deposit_verify(req: DepositSubmit):
    try:
        txid = req.txid.strip()
        if not txid:
            return {"status": "error", "message": "TxID is empty"}
            
        async with async_session() as session:
            # Fetch Binance credentials from DB
            from config import BINANCE_API_KEY, BINANCE_API_SECRET
            
            key_obj = (await session.execute(select(AppSetting).where(AppSetting.key == "BINANCE_API_KEY"))).scalar_one_or_none()
            sec_obj = (await session.execute(select(AppSetting).where(AppSetting.key == "BINANCE_API_SECRET"))).scalar_one_or_none()
            
            final_key = key_obj.value if key_obj and key_obj.value else BINANCE_API_KEY
            final_sec = sec_obj.value if sec_obj and sec_obj.value else BINANCE_API_SECRET

            # Check if this txid was already processed
            existing = (await session.execute(select(Deposit).where(Deposit.txid == txid))).scalar_one_or_none()
            if existing:
                return {"status": "error", "message": "Transaction verification failed. Please check the ID or contact support."}
                
            # Verify with Binance
            is_valid, msg, amount = await check_binance_deposit(txid, final_key, final_sec)
            if not is_valid:
                return {"status": "error", "message": "Transaction verification failed. Please check the ID or contact support."}
                
            # Update user balance
            user = (await session.execute(select(User).where(User.id == req.user_id))).scalar_one_or_none()
            if not user:
                return {"status": "error", "message": "User not found."}
                
            user.balance_store += amount
            
            # Save deposit
            new_deposit = Deposit(user_id=user.id, amount=amount, txid=txid, method=req.method)
            session.add(new_deposit)
            
            # Also log as a Transaction (optional, but good for history)
            tx = Transaction(user_id=user.id, type=TransactionType.DEPOSIT, amount=amount)
            session.add(tx)
            
            await session.commit()
            
            # Send notification via Bot (if available)
            # try:
            #     bot_buyer = app.state.bot_buyer
            #     if bot_buyer:
            #         await bot_buyer.send_message(
            #             chat_id=user.id,
            #             text=f"✅ **تم الإيداع بنجاح!**\n\n💰 المبلغ: **${amount}**\n🔖 رقم المعاملة: `{txid}`\nرصيدك الحالي: **${user.balance_store:.2f}**",
            #             parse_mode="Markdown"
            #         )
            # except: pass
            
            return {"status": "success", "message": f"Successfully deposited ${amount}", "new_balance": user.balance_store}
            
    except Exception as e:
        logger.error(f"Deposit Verify Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/admin/sourcing/data")
async def get_sourcing_data():
    try:
        async with async_session() as session:
            total_sourced = (await session.execute(select(func.count(Account.id)))).scalar() or 0
            pending_count = (await session.execute(select(func.count(Account.id)).where(Account.status == AccountStatus.PENDING))).scalar() or 0
            accepted_sourced = (await session.execute(select(func.count(Account.id)).where(Account.status.in_([AccountStatus.AVAILABLE, AccountStatus.SOLD])))).scalar() or 0
            available_count = (await session.execute(select(func.count(Account.id)).where(Account.status == AccountStatus.AVAILABLE))).scalar() or 0
            sold_count = (await session.execute(select(func.count(Account.id)).where(Account.status == AccountStatus.SOLD))).scalar() or 0
            rejected_sourced = (await session.execute(select(func.count(Account.id)).where(Account.status == AccountStatus.REJECTED))).scalar() or 0
            
            # Withdrawal stats
            withdraw_pending = (await session.execute(select(func.count(WithdrawalRequest.id)).where(WithdrawalRequest.status == WithdrawalStatus.PENDING))).scalar() or 0
            withdraw_approved = (await session.execute(select(func.count(WithdrawalRequest.id)).where(WithdrawalRequest.status == WithdrawalStatus.APPROVED))).scalar() or 0
            withdraw_rejected = (await session.execute(select(func.count(WithdrawalRequest.id)).where(WithdrawalStatus.REJECTED == WithdrawalRequest.status))).scalar() or 0
            total_paid_amount = (await session.execute(select(func.sum(WithdrawalRequest.amount)).where(WithdrawalRequest.status == WithdrawalStatus.APPROVED))).scalar() or 0
            withdraw_pending_amount = (await session.execute(select(func.sum(WithdrawalRequest.amount)).where(WithdrawalRequest.status == WithdrawalStatus.PENDING))).scalar() or 0
            
            # User stats
            total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
            banned_users = (await session.execute(select(func.count(User.id)).where(User.is_banned_sourcing == True))).scalar() or 0
            active_users = total_users - banned_users
            
            # Custom User Prices stats (Unique Users & Countries)
            from sqlalchemy import distinct
            total_custom_prices = (await session.execute(select(func.count(distinct(UserCountryPrice.user_id))))).scalar() or 0
            total_custom_countries = (await session.execute(select(func.count(distinct(UserCountryPrice.iso_code))))).scalar() or 0
            
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
                    "date": a.created_at.isoformat() if a.created_at else None
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
            db_users = users_result.scalars().all()
            
            # Get seller stats for these users
            u_ids = [u.id for u in db_users]
            seller_stats = {uid: {"sold": 0, "accepted": 0, "rejected": 0} for uid in u_ids}
            if u_ids:
                sold_stmt = select(Account.seller_id, func.count(Account.id)).where(Account.seller_id.in_(u_ids), Account.status == AccountStatus.SOLD).group_by(Account.seller_id)
                acc_stmt = select(Account.seller_id, func.count(Account.id)).where(Account.seller_id.in_(u_ids), Account.status == AccountStatus.AVAILABLE).group_by(Account.seller_id)
                rej_stmt = select(Account.seller_id, func.count(Account.id)).where(Account.seller_id.in_(u_ids), Account.status == AccountStatus.REJECTED).group_by(Account.seller_id)
                
                for rid, cnt in (await session.execute(sold_stmt)).all(): seller_stats[rid]["sold"] = cnt
                for rid, cnt in (await session.execute(acc_stmt)).all(): seller_stats[rid]["accepted"] = cnt
                for rid, cnt in (await session.execute(rej_stmt)).all(): seller_stats[rid]["rejected"] = cnt

            users_list = []
            for u in db_users:
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
                    "available_count": available_count,
                    "sold_count": sold_count,
                    "accepted_sourced": accepted_sourced,
                    "rejected_sourced": rejected_sourced,
                    "total_balance": round(total_sourcing_balance, 2),
                    "user_count": user_count,
                    "withdraw_pending": withdraw_pending,
                    "withdraw_approved": withdraw_approved,
                    "withdraw_rejected": withdraw_rejected,
                    "withdraw_pending_amount": float(withdraw_pending_amount),
                    "total_paid_amount": float(total_paid_amount),
                    "total_users": total_users,
                    "active_users": active_users,
                    "banned_users": banned_users,
                    "total_custom_prices": total_custom_prices,
                    "total_custom_countries": total_custom_countries
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
            banned_users = (await session.execute(select(func.count(User.id)).where(User.is_banned_store == True))).scalar() or 0
            active_users = user_count - banned_users
            stock_count = (await session.execute(select(func.count(Account.id)).where(Account.status == AccountStatus.AVAILABLE))).scalar() or 0
            total_balance = (await session.execute(select(func.sum(User.balance_store)))).scalar() or 0.0

            # Sales stats
            total_sales_count = (await session.execute(select(func.count(Account.id)).where(Account.status == AccountStatus.SOLD))).scalar() or 0
            total_revenue = (await session.execute(select(func.sum(Account.price)).where(Account.status == AccountStatus.SOLD))).scalar() or 0.0

            # Deposit stats
            total_deposit_requests = (await session.execute(select(func.count(Deposit.id)))).scalar() or 0
            total_deposits_amount = (await session.execute(select(func.sum(Deposit.amount)))).scalar() or 0.0

            # Price stats
            active_countries_count = (await session.execute(select(func.count(CountryPrice.id)).where(CountryPrice.price > 0))).scalar() or 0
            min_price = (await session.execute(select(func.min(CountryPrice.price)).where(CountryPrice.price > 0))).scalar() or 0.0
            max_price = (await session.execute(select(func.max(CountryPrice.price)).where(CountryPrice.price > 0))).scalar() or 0.0

            # Custom User stats
            from sqlalchemy import distinct
            total_custom_users = (await session.execute(select(func.count(distinct(UserStorePrice.user_id))))).scalar() or 0
            total_custom_countries = (await session.execute(select(func.count(distinct(UserStorePrice.iso_code))))).scalar() or 0

            users_result = await session.execute(select(User).order_by(User.id.desc()).limit(200))
            all_users_raw = users_result.scalars().all()
            u_ids = [u.id for u in all_users_raw]

            # Optimized bulk stats for users
            bought_stats = {uid: 0 for uid in u_ids}
            spent_stats = {uid: 0.0 for uid in u_ids}

            if u_ids:
                # Count bought numbers per user
                b_stmt = select(Account.buyer_id, func.count(Account.id)).where(Account.buyer_id.in_(u_ids)).group_by(Account.buyer_id)
                for rid, cnt in (await session.execute(b_stmt)).all(): bought_stats[rid] = cnt

                # Sum spent amount per user
                s_stmt = select(Transaction.user_id, func.sum(Transaction.amount)).where(
                    Transaction.user_id.in_(u_ids),
                    Transaction.type == TransactionType.BUY
                ).group_by(Transaction.user_id)
                for rid, val in (await session.execute(s_stmt)).all(): spent_stats[rid] = abs(float(val or 0))

            users = [
                {
                    "id": u.id,
                    "full_name": u.full_name or "N/A",
                    "username": f"@{u.username}" if u.username else "N/A",
                    "balance_store": round(u.balance_store or 0.0, 2),
                    "balance_sourcing": round(u.balance_sourcing or 0.0, 2),
                    "join_date": u.join_date.strftime("%Y-%m-%d") if u.join_date else "N/A",
                    "banned": u.is_banned_store,
                    "purchased_count": bought_stats[u.id],
                    "total_spent": round(spent_stats[u.id], 2),
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
                    "country": f"{flag} {acc.country}",
                    "date": acc.purchased_at.isoformat() if acc.purchased_at else None
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
            "stats": {
                "user_count": user_count,
                "banned_users": banned_users,
                "active_users": active_users,
                "stock_count": stock_count,
                "total_balance": total_balance,
                "total_sales_count": total_sales_count,
                "total_revenue": total_revenue,
                "total_deposit_requests": total_deposit_requests,
                "total_deposits_amount": total_deposits_amount,
                "active_countries_count": active_countries_count,
                "total_custom_users": total_custom_users,
                "total_custom_countries": total_custom_countries,
                "min_price": min_price,
                "max_price": max_price
            },
            "users": users,
            "transactions": transactions,
            "prices": prices
        }
    except Exception as e:
        logger.error(f"Store Admin Data Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/system/cleanup-fake")
async def cleanup_fake_api(key: str = None):
    if key != "cleanup_99":
        return {"status": "error", "message": "Invalid key"}
    try:
        async with async_session() as session:
            # Delete accounts with our dummy session strings
            await session.execute(text("DELETE FROM accounts WHERE session_string LIKE 'SEED_%' OR session_string = 'DUMMY_SESSION_STRING' OR session_string = 'SEED_DUMMY_SESSION'"))
            await session.commit()
            return {"status": "success", "message": "Cleanup complete. Fake data removed."}
    except Exception as e:
        logger.error(f"Cleanup API Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/admin/store/settings")
async def get_store_settings():
    try:
        from config import BINANCE_API_KEY, BINANCE_API_SECRET, DEPOSIT_ADDRESS
        async with async_session() as session:
            keys = [
                "BINANCE_API_KEY", "BINANCE_API_SECRET", 
                "BINANCE_PAY_ID", "TRX_ADDRESS", "USDT_BEP20_ADDRESS"
            ]
            settings = {}
            for k in keys:
                obj = (await session.execute(select(AppSetting).where(AppSetting.key == k))).scalar_one_or_none()
                settings[k] = obj.value if obj else ""
            
            # Fallbacks
            api_key = settings.get("BINANCE_API_KEY") or BINANCE_API_KEY
            api_secret = settings.get("BINANCE_API_SECRET") or BINANCE_API_SECRET
            
            # Return a placeholder for the secret so the user knows it is set but cannot see it
            masked_secret = "Already Set (Leave empty to keep current)" if api_secret else ""

            return {
                "binance_api_key": api_key,
                "binance_api_secret_masked": masked_secret,
                "binance_pay_id": settings.get("BINANCE_PAY_ID") or DEPOSIT_ADDRESS,
                "trx_address": settings.get("TRX_ADDRESS") or "",
                "usdt_bep20_address": settings.get("USDT_BEP20_ADDRESS") or ""
            }
    except Exception as e:
        logger.error(f"Get Store Settings Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/store/settings")
async def save_store_settings(req: StoreSettingsSubmit):
    try:
        async with async_session() as session:
            updates = {
                "BINANCE_API_KEY": req.binance_api_key.strip(),
                "BINANCE_PAY_ID": req.binance_pay_id.strip(),
                "TRX_ADDRESS": req.trx_address.strip(),
                "USDT_BEP20_ADDRESS": req.usdt_bep20_address.strip()
            }
            if req.binance_api_secret and "Already Set" not in req.binance_api_secret:
                updates["BINANCE_API_SECRET"] = req.binance_api_secret.strip()

            for k, v in updates.items():
                obj = (await session.execute(select(AppSetting).where(AppSetting.key == k))).scalar_one_or_none()
                if obj:
                    obj.value = v
                else:
                    new_setting = AppSetting(key=k, value=v)
                    session.add(new_setting)
            
            await session.commit()
            return {"status": "success", "message": "Settings saved successfully"}
    except Exception as e:
        logger.error(f"Save Store Settings Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/admin/store/deposits")
async def get_store_deposits():
    from database.models import Deposit, User
    async with async_session() as session:
        result = await session.execute(
            select(Deposit, User)
            .join(User, Deposit.user_id == User.id)
            .order_by(Deposit.created_at.desc())
        )
        data = []
        for dep, user in result.all():
            data.append({
                "id": dep.id,
                "user_id": user.id,
                "user_name": user.full_name or "N/A",
                "user_handle": f"@{user.username}" if user.username else "N/A",
                "amount": dep.amount,
                "txid": dep.txid,
                "method": dep.method or "Binance Pay",
                "date": dep.created_at.isoformat() if dep.created_at else None
            })
        return {"deposits": data}

@app.get("/api/admin/store/user-prices")
async def get_store_user_prices():
    from database.models import UserStorePrice, User
    async with async_session() as session:
        result = await session.execute(
            select(UserStorePrice, User)
            .join(User, UserStorePrice.user_id == User.id)
            .order_by(UserStorePrice.created_at.desc())
        )
        data = []
        for usp, user in result.all():
            flag = "🌐"
            name = f"Code {usp.country_code}"
            iso = usp.iso_code if usp.iso_code and usp.iso_code != 'XX' else None
            try:
                import pycountry
                if iso:
                    from web_admin import get_flag_emoji
                    flag = get_flag_emoji(iso)
                    country = pycountry.countries.get(alpha_2=iso)
                    if country:
                        name = country.name
                        import re
                        name = re.sub(r'\s*\(\?[A-Z]{2,3}\)?\s*$', '', name).strip()
                else:
                    n, f, _ = resolve_country_info(usp.country_code)
                    if n != "Unknown":
                        name = n
                        flag = f
            except: pass
            
            data.append({
                "id": usp.id,
                "user_id": user.id,
                "user_name": user.full_name or "N/A",
                "user_handle": f"@{user.username}" if user.username else "N/A",
                "country_code": usp.country_code,
                "iso_code": usp.iso_code,
                "country_name": f"{flag} {name}",
                "sell_price": usp.sell_price,
                "date": usp.created_at.isoformat() if usp.created_at else None
            })
        return {"prices": data}

@app.post("/api/admin/store/user-prices")
async def add_store_user_price(data: UserStorePriceCreate):
    from database.models import UserStorePrice, User
    async with async_session() as session:
        user = await session.get(User, data.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        if data.id:
            usp = await session.get(UserStorePrice, data.id)
            if not usp:
                raise HTTPException(status_code=404, detail="Price record not found")
            usp.sell_price = data.sell_price
            usp.country_code = data.country_code
            usp.iso_code = data.iso_code
        else:
            stmt = select(UserStorePrice).where(
                UserStorePrice.user_id == data.user_id,
                UserStorePrice.country_code == data.country_code,
                UserStorePrice.iso_code == data.iso_code
            )
            existing = (await session.execute(stmt)).scalar()
            if existing:
                raise HTTPException(status_code=400, detail="This country is already added for this user. Please edit the existing entry instead.")
            
            new_usp = UserStorePrice(
                user_id=data.user_id,
                country_code=data.country_code,
                iso_code=data.iso_code,
                sell_price=data.sell_price
            )
            session.add(new_usp)
        await session.commit()
        return {"status": "success"}

@app.delete("/api/admin/store/user-prices/{id}")
async def delete_store_user_price(id: int):
    from database.models import UserStorePrice
    async with async_session() as session:
        usp = await session.get(UserStorePrice, id)
        if usp:
            await session.delete(usp)
            await session.commit()
            return {"status": "success"}
        raise HTTPException(status_code=404, detail="Not found")

@app.get("/api/admin/store/servers")
async def get_servers():
    async with async_session() as session:
        stmt = select(ApiServer).order_by(ApiServer.id.asc())
        servers = (await session.execute(stmt)).scalars().all()
        return {"servers": [
            {
                "id": s.id,
                "name": s.name,
                "url": s.url,
                "api_key": s.api_key,
                "server_type": getattr(s, 'server_type', 'standard'),
                "extra_id": getattr(s, 'extra_id', ''),
                "profit_margin": s.profit_margin,
                "is_active": s.is_active
            } for s in servers
        ]}

@app.post("/api/admin/store/servers")
async def save_server(data: ApiServerSubmit):
    logger.info(f"Saving server: {data.dict()}")
    async with async_session() as session:
        if data.id:
            srv = await session.get(ApiServer, data.id)
            if not srv: raise HTTPException(status_code=404, detail="Server not found")
            srv.name = data.name
            srv.url = data.url
            srv.api_key = data.api_key
            srv.server_type = data.server_type
            srv.extra_id = data.extra_id
            srv.profit_margin = data.profit_margin
            srv.is_active = data.is_active
        else:
            srv = ApiServer(
                name=data.name,
                url=data.url,
                api_key=data.api_key,
                server_type=data.server_type,
                extra_id=data.extra_id,
                profit_margin=data.profit_margin,
                is_active=data.is_active
            )
            session.add(srv)
        await session.commit()
        return {"status": "success"}

@app.delete("/api/admin/store/servers/{id}")
async def delete_server(id: int):
    async with async_session() as session:
        srv = await session.get(ApiServer, id)
        if srv:
            await session.delete(srv)
            await session.commit()
            return {"status": "success"}
        raise HTTPException(status_code=404, detail="Not found")
@app.post("/api/admin/stock/start-login")
async def start_login(data: StockLoginStart):
    from services.session_manager import request_app_code
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
        # Match by both code and ISO for accurate price lookup
        stmt = select(CountryPrice).where(
            CountryPrice.country_code == country_code,
            CountryPrice.iso_code == iso_code
        )
        cp = (await session.execute(stmt)).scalar()
        if not cp:
             # Fallback to code only
             cp = (await session.execute(select(CountryPrice).where(CountryPrice.country_code == country_code))).scalar()
        
        price = cp.price if cp else 1.0
        
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
    from services.session_manager import submit_app_code
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
                "approve_delay": ucp.approve_delay,
                "date": ucp.created_at.isoformat() if ucp.created_at else None
            })
        return {"prices": data}

@app.post("/api/admin/sourcing/user-prices")
async def add_user_price(data: UserPriceCreate):
    from database.models import UserCountryPrice, User
    async with async_session() as session:
        user = await session.get(User, data.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        if data.id:
            # Explicit Update
            ucp = await session.get(UserCountryPrice, data.id)
            if not ucp:
                raise HTTPException(status_code=404, detail="Price record not found")
            ucp.buy_price = data.buy_price
            ucp.approve_delay = data.approve_delay
            # If they changed the country/iso in the modal (though UI might prevent it)
            ucp.country_code = data.country_code
            ucp.iso_code = data.iso_code
        else:
            # Check for Duplicate before adding new
            stmt = select(UserCountryPrice).where(
                UserCountryPrice.user_id == data.user_id,
                UserCountryPrice.country_code == data.country_code,
                UserCountryPrice.iso_code == data.iso_code
            )
            existing = (await session.execute(stmt)).scalar()
            if existing:
                raise HTTPException(status_code=400, detail="This country is already added for this user. Please edit the existing entry instead.")
                
            new_ucp = UserCountryPrice(
                user_id=data.user_id,
                country_code=data.country_code,
                iso_code=data.iso_code,
                buy_price=data.buy_price,
                approve_delay=data.approve_delay
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
            
            # Get custom user prices (organized by code and ISO)
            from database.models import UserCountryPrice
            custom_prices_result = await session.execute(select(UserCountryPrice).where(UserCountryPrice.user_id == user_id))
            custom_rows = custom_prices_result.scalars().all()
            
            # Key: (country_code, iso_code)
            custom_prices = {(cp.country_code, cp.iso_code): cp.buy_price for cp in custom_rows}
            
            formatted_prices = []
            seen_codes = set()
            
            # First, add global prices, applying custom overrides if they exist
            for p in prices:
                try:
                    iso = getattr(p, 'iso_code', None) or 'XX'
                    flag = get_flag_emoji(iso)
                    default_name = resolve_country_info(p.country_code)[0]
                    name = p.country_name if p.country_name and p.country_name != "Unknown" else default_name
                    
                    # Resolve price: Specific ISO override > Generic XX override > Global price
                    price_val = custom_prices.get((p.country_code, iso), 
                                                custom_prices.get((p.country_code, 'XX'), p.buy_price))
                    
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
            for (cc, c_iso), cp_buy_price in custom_prices.items():
                # Avoid duplicates if already added via the global prices loop
                if cc not in seen_codes and cp_buy_price > 0:
                    try:
                        # Use the specific ISO if available, else XX
                        n, f, _ = resolve_country_info(cc)
                        name = n if n != "Unknown" else f"Code {cc}"
                        
                        # If a custom ISO was specified, try to get a better name/flag
                        if c_iso != 'XX':
                            flag = get_flag_emoji(c_iso)
                        else:
                            flag = f

                        formatted_prices.append({
                            "name": name,
                            "flag": flag,
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
    from services.session_manager import request_app_code
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

        # 2. Country & Pricing Check
        try:
            # Clean phone and parse
            phone_p = phone if phone.startswith("+") else "+" + phone
            parsed = phonenumbers.parse(phone_p)
            cc = str(parsed.country_code)
            target_iso = phonenumbers.region_code_for_number(parsed) or 'XX'
            
            async with async_session() as session:
                from sqlalchemy import or_
                # Fetch all possible price candidates for this country code
                # This covers both specific ISO and global 'XX' entries
                
                # Resilient code matching
                cc_clean = cc.lstrip("+")
                cc_plus = "+" + cc_clean
                
                logger.info(f"OTP Request: User={data.user_id}, CC={cc}, ISO={target_iso}")
                
                # Check User Specific Prices first
                ucp_stmt = select(UserCountryPrice).where(
                    UserCountryPrice.user_id == data.user_id,
                    or_(UserCountryPrice.country_code == cc_clean, UserCountryPrice.country_code == cc_plus)
                )
                ucp_list = (await session.execute(ucp_stmt)).scalars().all()
                logger.info(f"OTP User Candidates: {[f'{u.country_code}/{u.iso_code}' for u in ucp_list]}")
                
                # Filter for best match
                # Priority: Exact ISO > Global XX > First available for this code
                ucp = next((u for u in ucp_list if u.iso_code == target_iso), 
                           next((u for u in ucp_list if u.iso_code == 'XX'), 
                                (ucp_list[0] if ucp_list else None)))
                
                # Check Global Prices
                cp_stmt = select(CountryPrice).where(
                    or_(CountryPrice.country_code == cc_clean, CountryPrice.country_code == cc_plus)
                )
                cp_list = (await session.execute(cp_stmt)).scalars().all()
                logger.info(f"OTP Global Candidates: {[f'{c.country_code}/{c.iso_code}' for c in cp_list]}")
                
                cp = next((c for c in cp_list if c.iso_code == target_iso), 
                          next((c for c in cp_list if c.iso_code == 'XX'), 
                               (cp_list[0] if cp_list else None)))
                
            # 3. Final Resolution
            final_buy_price = ucp.buy_price if ucp else (cp.buy_price if cp else 0)
            
            if final_buy_price <= 0:
                raise HTTPException(status_code=400, detail="Sorry, this country is not requested at the moment.")
                
            # Clean number for Telegram (E164)
            phone_clean = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                    
        except HTTPException as he: raise he
        except Exception as e:
            logger.error(f"Sourcing Price Error: {e}")
            raise HTTPException(status_code=400, detail="Error detecting country price. Please check number format.")

        phone_code_hash = await request_app_code(data.user_id, phone_clean)
        return {"hash": phone_code_hash, "phone": phone_clean}
    except Exception as e:
        logger.error(f"Seller OTP Request Error: {e}")
        if isinstance(e, HTTPException): raise e
        err_msg = str(e)
        if any(x in err_msg.lower() for x in ["banned", "frozen", "security"]):
             raise HTTPException(status_code=400, detail=err_msg)
        raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")

@app.post("/api/seller/submit-otp")
async def seller_submit_otp(data: SellerOTPSubmit):
    from services.session_manager import submit_app_code
    try:
        session_string = await submit_app_code(data.user_id, data.phone, data.hash, data.code)
        
        if not session_string:
            raise HTTPException(status_code=400, detail="Verification failed. The code is incorrect or has expired.")
            
        async with async_session() as session:
            # Automatic price detection
            price = 0
            try:
                phone_p = data.phone if data.phone.startswith("+") else "+" + data.phone
                parsed = phonenumbers.parse(phone_p)
                cc = str(parsed.country_code)
                target_iso = phonenumbers.region_code_for_number(parsed) or 'XX'
                
                # Resilient code matching
                cc_clean = cc.lstrip("+")
                cc_plus = "+" + cc_clean
                
                # 1. User Price
                ucp_stmt = select(UserCountryPrice).where(
                    UserCountryPrice.user_id == data.user_id,
                    or_(UserCountryPrice.country_code == cc_clean, UserCountryPrice.country_code == cc_plus)
                )
                ucp_list = (await session.execute(ucp_stmt)).scalars().all()
                ucp = next((u for u in ucp_list if u.iso_code == target_iso), 
                           next((u for u in ucp_list if u.iso_code == 'XX'), 
                                (ucp_list[0] if ucp_list else None)))
                
                # 2. Global Price
                cp_stmt = select(CountryPrice).where(
                    or_(CountryPrice.country_code == cc_clean, CountryPrice.country_code == cc_plus)
                )
                cp_list = (await session.execute(cp_stmt)).scalars().all()
                cp = next((c for c in cp_list if c.iso_code == target_iso), 
                          next((c for c in cp_list if c.iso_code == 'XX'), 
                               (cp_list[0] if cp_list else None)))
                
                price = ucp.buy_price if ucp else (cp.buy_price if cp else 0)
            except Exception as e:
                logger.error(f"Submit Price Detection Error: {e}")

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
                "date": r.created_at.isoformat() if r.created_at else None
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
                "date": r.created_at.isoformat() if r.created_at else None
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
async def detect_country(phone: str, user_id: int = 0):
    try:
        # Clean input
        raw = phone.strip().lstrip('+')
        if not raw: return {"found": False}
        
        # Immediate CC detection (best for short input like +20)
        detected_cc = None
        for i in range(4, 0, -1):
            prefix = raw[:i]
            if prefix.isdigit() and int(prefix) in phonenumbers.COUNTRY_CODE_TO_REGION_CODE:
                detected_cc = prefix
                break
        
        # Fallback to full parsing if it's a long number
        target_iso = 'XX'
        try:
            phone_p = phone if phone.startswith('+') else f"+{phone}"
            parsed = phonenumbers.parse(phone_p)
            detected_cc = str(parsed.country_code)
            target_iso = phonenumbers.region_code_for_number(parsed) or 'XX'
        except: pass

        if not detected_cc:
            return {"found": False}
            
        async with async_session() as session:
            from sqlalchemy import or_
            cc_clean = detected_cc.lstrip("+")
            cc_plus = "+" + cc_clean
            
            # 1. Custom User Price
            ucp = None
            if user_id > 0:
                ucp_stmt = select(UserCountryPrice).where(
                    UserCountryPrice.user_id == user_id,
                    or_(UserCountryPrice.country_code == cc_clean, UserCountryPrice.country_code == cc_plus)
                )
                ucp_list = (await session.execute(ucp_stmt)).scalars().all()
                ucp = next((u for u in ucp_list if u.iso_code == target_iso), 
                           next((u for u in ucp_list if u.iso_code == 'XX'), 
                                (ucp_list[0] if ucp_list else None)))
            
            # 2. Global Price
            cp_stmt = select(CountryPrice).where(
                or_(CountryPrice.country_code == cc_clean, CountryPrice.country_code == cc_plus)
            )
            cp_list = (await session.execute(cp_stmt)).scalars().all()
            cp = next((c for c in cp_list if c.iso_code == target_iso), 
                      next((c for c in cp_list if c.iso_code == 'XX'), 
                           (cp_list[0] if cp_list else None)))
            
            # Resolution
            price_val = ucp.buy_price if ucp else (cp.buy_price if cp else 0)
            
            if price_val > 0:
                # Resolve Name & Flag
                display_iso = target_iso
                if display_iso == 'XX':
                    display_iso = phonenumbers.region_code_for_country_code(int(detected_cc))
                
                name = cp.country_name if cp else (ucp.country_name if hasattr(ucp, 'country_name') else "Requested Country")
                if not cp and ucp:
                    n, _, _ = resolve_country_info(detected_cc)
                    name = n if n != "Unknown" else f"Code {detected_cc}"

                return {
                    "found": True,
                    "name": name,
                    "flag": get_flag_emoji(display_iso) if display_iso != 'XX' else "🌐",
                    "price": price_val
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
                "date": a.created_at.isoformat() if a.created_at else None
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
                "date": a.created_at.isoformat() if a.created_at else None
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
