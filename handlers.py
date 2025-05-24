# hr_llm_bot/handlers.py
from promt import get_main_system_prompt
# hr_llm_bot/handlers.py
from typing import List, Dict, Any

from aiogram import F, Router, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from langchain_core.messages import BaseMessage

from llm_service import LLMService
from states import InterviewStates
from config import AVAILABLE_POSITIONS, INCOMPETENT_VERDICT, MAX_MESSAGES_PER_SIDE

router = Router()

# Инициализация LLM сервиса
llm_s = None
try:
    llm_s = LLMService()
except Exception:
    # Логирование здесь было бы полезно, но по запросу оно убрано
    pass


# --- Вспомогательная функция для проверки, не от себя ли сообщение ---
async def is_message_from_self(message: Message) -> bool:
    if not message.from_user:  # Сообщения от каналов (анонимные) или другие особые случаи
        # Если бот сам постит от имени канала, message.from_user может не быть.
        # message.sender_chat.id == message.chat.id может быть признаком этого.
        # Но для сценария "два бота", боты обычно имеют from_user.
        # Если кандидат-бот постит как канал, нужна другая логика различения.
        # Пока предполагаем, что боты идентифицируются через from_user.
        return False  # Не можем точно сказать, лучше обработать
    me = await message.bot.get_me()
    return message.from_user.id == me.id


# --- Системный промпт (из предыдущего ответа) ---



# --- Обработчики ---

@router.channel_post(
    Command("start"))  # Для администратора канала, чтобы сбросить/инициализировать состояние бота для канала
async def cmd_start_channel(message: Message, state: FSMContext):
    if await is_message_from_self(message):
        return

    # Эта команда не для кандидата, а для управления ботом в канале.
    # Например, админ может "перезапустить" интервью для канала.
    await state.clear()
    await state.set_state(InterviewStates.waiting_for_position)
    initial_system_prompt = get_main_system_prompt()
    await state.update_data(
        dialog_history_raw=[{"role": "system", "content": initial_system_prompt}],
        message_count_candidate=0
    )
    # Бот не отвечает на эту команду в канал, чтобы не мешать.
    # Можно отправить подтверждение в личку администратору, если это необходимо.


# Обработчик для самого первого сообщения от кандидата в канале, если нет активного диалога
@router.channel_post(F.text, StateFilter(None))  # StateFilter(None) - нет установленного состояния
async def handle_first_candidate_post(message: Message, state: FSMContext):
    if await is_message_from_self(message):
        return

    # Это первое сообщение от кандидата в "чистом" канале (с точки зрения FSM бота)
    # Устанавливаем начальное состояние и системный промпт
    await state.set_state(InterviewStates.waiting_for_position)
    initial_system_prompt = get_main_system_prompt()
    await state.update_data(
        dialog_history_raw=[{"role": "system", "content": initial_system_prompt}],
        message_count_candidate=0  # будет увеличен в process_initial_message
    )

    # Теперь передаем это же сообщение на обработку как первое сообщение с позицией
    await process_initial_message(message, state)


@router.channel_post(F.text, InterviewStates.waiting_for_position)
async def process_initial_message(message: Message, state: FSMContext):
    if await is_message_from_self(message):  # Дополнительная проверка, если вызван напрямую
        return

    user_text = message.text.strip()

    if not llm_s:
        await message.answer("Извините, сервис для обработки запросов временно недоступен. Попробуйте позже.")
        return

    current_data = await state.get_data()
    dialog_history_raw: List[Dict[str, Any]] = current_data.get('dialog_history_raw', [])
    # Убедимся, что системный промпт есть, если его не установил handle_first_candidate_post
    # (хотя по логике он должен быть установлен)
    if not dialog_history_raw or dialog_history_raw[0]['role'] != 'system':
        system_prompt_content = get_main_system_prompt()
        dialog_history_raw = [{"role": "system", "content": system_prompt_content}]

    history_for_llm: List[BaseMessage] = llm_s.history_to_langchain_format(dialog_history_raw)

    bot_response_text = await llm_s.get_llm_response(history_for_llm, user_input=user_text)

    # Это первое сообщение от кандидата, засчитываем
    await state.update_data(message_count_candidate=1)
    current_data = await state.get_data()  # Перечитываем данные после обновления счетчика
    dialog_history_raw = current_data.get('dialog_history_raw', [])  # и истории (если она могла измениться)

    if bot_response_text and "ошибка" not in bot_response_text.lower():
        updated_dialog_history_raw = llm_s.add_message_to_raw_history(list(dialog_history_raw), "user", user_text)
        updated_dialog_history_raw = llm_s.add_message_to_raw_history(updated_dialog_history_raw, "assistant",
                                                                      bot_response_text)

        await state.update_data(
            dialog_history_raw=updated_dialog_history_raw
            # message_count_candidate уже обновлен
        )
        # Ответ бота отправляется в канал
        await message.answer(bot_response_text)
        await state.set_state(InterviewStates.interview_in_progress)
    else:
        # Если ошибка, состояние остается waiting_for_position, чтобы кандидат мог попробовать снова.
        # message_count_candidate уже 1, при следующей попытке он станет 1 снова (если state.clear() не было)
        # или будет проблемой. Лучше сбрасывать счетчик или не инкрементить при ошибке.
        # Для простоты пока так, но здесь может потребоваться более тонкая логика.
        await message.answer(
            "Произошла ошибка при обработке вашего первого сообщения или позиция не распознана. Пожалуйста, попробуйте еще раз или администратор может перезапустить сессию командой /start.")


@router.channel_post(F.text, InterviewStates.interview_in_progress)
async def process_interview_message(message: Message, state: FSMContext):
    if await is_message_from_self(message):
        return

    user_text = message.text.strip()

    if not llm_s:
        await message.answer("Извините, сервис для обработки запросов временно недоступен. Попробуйте позже.")
        return

    current_data = await state.get_data()
    dialog_history_raw: List[Dict[str, Any]] = current_data.get('dialog_history_raw', [])
    message_count_candidate: int = current_data.get('message_count_candidate', 0)

    message_count_candidate += 1

    history_for_llm_call: List[BaseMessage] = llm_s.history_to_langchain_format(dialog_history_raw)
    user_input_for_llm = user_text

    bot_response_text = await llm_s.get_llm_response(history_for_llm_call, user_input=user_input_for_llm)

    if bot_response_text and "ошибка" not in bot_response_text.lower():
        updated_dialog_history_raw = llm_s.add_message_to_raw_history(list(dialog_history_raw), "user", user_text)
        updated_dialog_history_raw = llm_s.add_message_to_raw_history(updated_dialog_history_raw, "assistant",
                                                                      bot_response_text)

        await state.update_data(
            dialog_history_raw=updated_dialog_history_raw,
            message_count_candidate=message_count_candidate
        )
        await message.answer(bot_response_text)

        if bot_response_text.startswith("[") and bot_response_text.endswith("]"):
            clean_verdict = bot_response_text.strip("[]")
            if clean_verdict in AVAILABLE_POSITIONS or clean_verdict == INCOMPETENT_VERDICT.strip("[]"):
                await state.set_state(InterviewStates.finished)
            else:
                if message_count_candidate >= MAX_MESSAGES_PER_SIDE:
                    await message.answer(
                        f"Модуль принятия решений дал непредвиденный ответ. Результат: {INCOMPETENT_VERDICT}")
                    await state.set_state(InterviewStates.finished)
        elif message_count_candidate >= MAX_MESSAGES_PER_SIDE:
            await message.answer(INCOMPETENT_VERDICT)
            await state.set_state(InterviewStates.finished)
    else:
        await state.update_data(message_count_candidate=message_count_candidate)
        await message.answer("Произошла ошибка при генерации ответа. Попробуйте ответить еще раз.")


@router.channel_post(F.text, InterviewStates.finished)
async def process_message_after_finish(message: Message, state: FSMContext):
    if await is_message_from_self(message):
        return
    await message.answer(
        "Собеседование уже завершено. Для начала нового диалога администратор канала может использовать команду /start.")


@router.channel_post(~F.text)  # Обработка нетекстовых сообщений в канале
async def handle_non_text_channel_post(message: Message):
    if await is_message_from_self(message):
        return
    # Можно добавить проверку, есть ли активное состояние, чтобы не спамить на каждое медиа
    # current_state = await state.get_state()
    # if current_state is not None:
    await message.answer("Пожалуйста, отправляйте только текстовые сообщения в рамках собеседования.")