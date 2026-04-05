from aiogram.fsm.state import State, StatesGroup

class SellAccountState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_code = State()
