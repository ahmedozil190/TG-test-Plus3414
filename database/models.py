from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum
from sqlalchemy.orm import declarative_base
import enum
from datetime import datetime

Base = declarative_base()

class AccountStatus(enum.Enum):
    AVAILABLE = "available"
    PENDING = "pending"
    SOLD = "sold"

class TransactionType(enum.Enum):
    DEPOSIT = "deposit"
    BUY = "buy"
    SELL = "sell"

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True) # Telegram User ID
    balance = Column(Float, default=0.0)
    language = Column(String, default="ar")
    join_date = Column(DateTime, default=datetime.utcnow)

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

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
