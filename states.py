from aiogram.fsm.state import State, StatesGroup

class InterviewStates(StatesGroup):
    waiting_for_position = State()    # Ожидание указания позиции
    interview_in_progress = State()   # Идет собеседование
    finished = State()                # Собеседование завершено