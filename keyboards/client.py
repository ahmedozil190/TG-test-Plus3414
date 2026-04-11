from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="- Buy an account.", callback_data="buy_number"),
            InlineKeyboardButton(text="- Selling an account.", callback_data="sell_number")
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
