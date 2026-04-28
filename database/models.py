from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum, Boolean, BigInteger
from sqlalchemy.orm import declarative_base
import enum
from datetime import datetime

Base = declarative_base()

class AccountStatus(enum.Enum):
    AVAILABLE = "available"
    PENDING = "pending"
    SOLD = "sold"
    REJECTED = "rejected"
    
class WithdrawalStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class TransactionType(enum.Enum):
    DEPOSIT = "deposit"
    BUY = "buy"
    SELL = "sell"
    WITHDRAW = "withdraw"

class User(Base):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True) # Telegram User ID
    balance_store = Column(Float, default=0.0)
    balance_sourcing = Column(Float, default=0.0)
    language = Column(String, default="ar")
    join_date = Column(DateTime, default=datetime.utcnow)
    full_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
     
    # Isolation flags
    is_active_store = Column(Boolean, default=False)
    is_active_sourcing = Column(Boolean, default=False)
    is_banned_store = Column(Boolean, default=False)
    is_banned_sourcing = Column(Boolean, default=False)

class Account(Base):
    __tablename__ = 'accounts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String, unique=True, nullable=False)
    country = Column(String, nullable=False)
    session_string = Column(String, nullable=True)
    status = Column(Enum(AccountStatus), default=AccountStatus.AVAILABLE)
    price = Column(Float, nullable=False)
    seller_id = Column(BigInteger, ForeignKey('users.id'), nullable=True)
    buyer_id = Column(BigInteger, ForeignKey('users.id'), nullable=True)
    otp_code = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    purchased_at = Column(DateTime, nullable=True)
    
    # New fields for external servers
    server_id = Column(Integer, ForeignKey('api_servers.id'), nullable=True)
    hash_code = Column(String, nullable=True)

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class CountryPrice(Base):
    __tablename__ = 'country_prices'
    id = Column(Integer, primary_key=True, autoincrement=True)
    country_code = Column(String, nullable=False) # e.g. "1" (Not unique anymore)
    iso_code = Column(String, default="XX") # e.g. "US", "CA"
    country_name = Column(String, nullable=False) # e.g. "Egypt"
    price = Column(Float, nullable=False, default=1.0) # Selling Price
    buy_price = Column(Float, nullable=False, default=0.5) # Buying Price from people
    approve_delay = Column(Integer, nullable=False, default=0) # Auto-approval delay in seconds
    log_quantity = Column(Integer, nullable=False, default=1000) # Quantity shown in channel log
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserCountryPrice(Base):
    __tablename__ = 'user_country_prices'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    country_code = Column(String, nullable=False) # e.g. "1"
    iso_code = Column(String, default="XX") # e.g. "US"
    buy_price = Column(Float, nullable=False)
    approve_delay = Column(Integer, nullable=False, default=0) # Custom auto-approval delay
    created_at = Column(DateTime, default=datetime.utcnow)

class UserStorePrice(Base):
    __tablename__ = 'user_store_prices'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    country_code = Column(String, nullable=False) # e.g. "1"
    iso_code = Column(String, default="XX") # e.g. "US"
    sell_price = Column(Float, nullable=False) # Custom discount selling price for buyers
    created_at = Column(DateTime, default=datetime.utcnow)


class WithdrawalRequest(Base):
    __tablename__ = 'withdrawal_requests'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=False)
    method = Column(String, nullable=False) # e.g. "TRX - TRC20"
    address = Column(String, nullable=False) # Wallet Address
    transaction_id = Column(String(12), unique=True, nullable=True) # e.g. "TC782794467F"
    status = Column(Enum(WithdrawalStatus), default=WithdrawalStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)

class Deposit(Base):
    __tablename__ = 'deposits'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=False)
    txid = Column(String, unique=True, nullable=False) # Binance TxID
    method = Column(String, nullable=True) # Payment Method
    created_at = Column(DateTime, default=datetime.utcnow)

class AppSetting(Base):
    __tablename__ = 'app_settings'
    key = Column(String, primary_key=True)
    value = Column(String, nullable=True)

class ApiServer(Base):
    __tablename__ = 'api_servers'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    api_key = Column(String, nullable=False)
    server_type = Column(String, default="standard") # 'standard' (Spider/Max) or 'lion' (TG-Lion)
    extra_id = Column(String, nullable=True) # For YourID in TG-Lion
    profit_margin = Column(Float, default=20.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)



class SubscriptionChannel(Base):
    __tablename__ = 'subscription_channels'
    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_type = Column(String, default="store") # 'store' or 'sourcing'
    username = Column(String, nullable=False) # e.g. "@OzZoOSMS"
    link = Column(String, nullable=False) # e.g. "https://t.me/OzZoOSMS"
    created_at = Column(DateTime, default=datetime.utcnow)
