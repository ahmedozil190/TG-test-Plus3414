from .start import router as start_router
from .wallet import router as wallet_router
from .sell import router as sell_router
from .buy import router as buy_router
from .admin import router as admin_router
from aiogram import Router

main_router = Router()
main_router.include_router(admin_router)
main_router.include_router(start_router)
main_router.include_router(wallet_router)
main_router.include_router(sell_router)
main_router.include_router(buy_router)
