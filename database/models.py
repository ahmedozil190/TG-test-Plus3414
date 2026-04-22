from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum, Boolean
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
    id = Column(Integer, primary_key=True) # Telegram User ID
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
    session_string = Column(String, nullable=False)
    status = Column(Enum(AccountStatus), default=AccountStatus.AVAILABLE)
    price = Column(Float, nullable=False)
    seller_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    buyer_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
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
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WithdrawalRequest(Base):
    __tablename__ = 'withdrawal_requests'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=False)
    method = Column(String, nullable=False) # e.g. "TRX - TRC20"
    address = Column(String, nullable=False) # Wallet Address
    transaction_id = Column(String(12), unique=True, nullable=True) # e.g. "TC782794467F"
    status = Column(Enum(WithdrawalStatus), default=WithdrawalStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
