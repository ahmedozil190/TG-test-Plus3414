from aiogram import Router
from .start import router as start_router
from .sell_logic import router as sell_logic_router
from .admin import router as admin_router

seller_router = Router()
seller_router.include_router(start_router)
seller_router.include_router(sell_logic_router)
seller_router.include_router(admin_router)
