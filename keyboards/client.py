from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Buy Account", callback_data="buy_number"),
            InlineKeyboardButton(text="Sell Account", callback_data="sell_number")
        ],
        [
            InlineKeyboardButton(text="Payout Money", callback_data="payout"),
            InlineKeyboardButton(text="TopUp Balance", callback_data="deposit")
        ],
        [
            InlineKeyboardButton(text="Countries we buy", callback_data="countries_we_buy"),
            InlineKeyboardButton(text="Sales channel", callback_data="sales_channel")
        ]
    ])

def profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ شحن الرصيد", callback_data="deposit")],
        [InlineKeyboardButton(text="الرجوع 🔙", callback_data="back_main")]
    ])
