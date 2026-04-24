from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from config import SELLER_URL, STORE_URL

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛒 Open Store | فتح المتجر", web_app=WebAppInfo(url=STORE_URL))
        ]
    ])

