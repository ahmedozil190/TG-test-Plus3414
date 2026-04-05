from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from database.engine import engine
from database.models import User, Account, Transaction
import os

app = FastAPI(title="Store Admin Panel")

# Secret key for session cookies
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-12345")

class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form.get("username"), form.get("password")

        # Basic authentication (In production, load these from .env)
        # We will use "admin" and "admin123" for now.
        if username == "admin" and password == "admin123":
            request.session.update({"token": "authenticated"})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")
        if not token:
            return False
        return True

authentication_backend = AdminAuth(secret_key=SECRET_KEY)
admin = Admin(app, engine, authentication_backend=authentication_backend, title="Store Admin")

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.balance, User.language, User.join_date]
    name_plural = "المستخدمين"
    icon = "fa-solid fa-users"
    can_create = True
    can_edit = True
    can_delete = True

class AccountAdmin(ModelView, model=Account):
    column_list = [Account.id, Account.phone_number, Account.country, Account.status, Account.price, Account.buyer_id]
    name_plural = "أرقام التلجرام"
    icon = "fa-solid fa-phone"
    can_create = True
    can_edit = True
    can_delete = True
    column_searchable_list = [Account.phone_number, Account.country]

class TransactionAdmin(ModelView, model=Transaction):
    column_list = [Transaction.id, Transaction.user_id, Transaction.type, Transaction.amount, Transaction.timestamp]
    name_plural = "العمليات المالية"
    icon = "fa-solid fa-money-bill-wave"
    can_create = False
    can_edit = False
    can_delete = True
    column_searchable_list = [Transaction.user_id]

admin.add_view(UserAdmin)
admin.add_view(AccountAdmin)
admin.add_view(TransactionAdmin)
