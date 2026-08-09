from aiogram.fsm.state import State, StatesGroup


class StandupStates(StatesGroup):
    waiting_today = State()
    waiting_tomorrow = State()
    preview = State()
