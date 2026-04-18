from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from config import SELLER_URL

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="- Buy an account.", callback_data="buy_number"),
            InlineKeyboardButton(text="- Selling an account.", web_app=WebAppInfo(url=SELLER_URL))
        ],
        [
            InlineKeyboardButton(text="Automatic payment.", callback_data="deposit")
        ],
        [
            InlineKeyboardButton(text="API KEY", callback_data="api_key")
        ],
        [
            InlineKeyboardButton(text="Customer service.", callback_data="customer_service")
        ],
        [
            InlineKeyboardButton(text="Bot activations.", url="https://t.me/MOOO8O"),
            InlineKeyboardButton(text="- Call link.", callback_data="call_link")
        ]
    ])

def profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ شحن الرصيد", callback_data="deposit")],
        [InlineKeyboardButton(text="الرجوع 🔙", callback_data="back_main")]
    ])

def sell_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="- Selling an account.", url="https://t.me/MOOO8O")],
        [InlineKeyboardButton(text="Account prices.", callback_data="sell_prices")],
        [InlineKeyboardButton(text="- Pull my balance.", callback_data="pull_balance")],
        [InlineKeyboardButton(text="Prices channel", url="https://t.me/MOOO8O")],
        [InlineKeyboardButton(text="- Return.", callback_data="back_main")]
    ])
