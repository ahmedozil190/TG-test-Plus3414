from aiogram.fsm.state import State, StatesGroup

class AdminState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_add_balance = State()
    waiting_for_sub_balance = State()
    waiting_for_broadcast = State()
