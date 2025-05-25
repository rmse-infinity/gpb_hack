import re
from typing import List, Dict

from aiogram import F, Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from llm_service import LLMService
from config import AVAILABLE_POSITIONS, INCOMPETENT_VERDICT
from promt5 import get_main_system_prompt

router = Router()

channel_states: Dict[int, 'ChannelState'] = {}

llm_s = LLMService()

ALL_QUESTIONS_LIST = [
    "1. ГДЕ РАНЬШЕ РАБОТАЛИ? (Укажите компании и сферу их деятельности)",
    "2. НА КАКОЙ ДОЛЖНОСТИ РАБОТАЛИ И КАК ДОЛГО В КАЖДОЙ КОМПАНИИ? (Перечислите ключевые обязанности и достижения по каждой значимой роли)",
    "3. ОПИШИТЕ ВАШ САМЫЙ СЛОЖНЫЙ ПРОЕКТ (детально, с указанием вашей роли, использованных технологий и результатов).",
    "4. В чем фундаментальное различие между обучением с учителем и без учителем? Приведите по одному бизнес-примеру для каждого.",
    "5. Опишите основные этапы конвейера данных (data pipeline) и значение хранилища данных (data warehouse) для аналитики.",
    "6. Для анализа оттока клиентов, какие ключевые метрики вы бы отслеживали и как извлекли бы из них пользу?",
    "7. Что такое дрейф модели (model drift)? Опишите по одной стратегии для его обнаружения и смягчения.",
    "8. Какую методологию управления проектами (Agile, Waterfall) вы бы выбрали для проекта с часто меняющимися требованиями и почему?",
    "9. Каковы проблемы переобучения (overfitting) и недообучения (underfitting) модели? Опишите по одному методу борьбы с каждой.",
    "10. Почему Git важен в совместных проектах с данными? Опишите сценарий, где его отсутствие привело бы к проблемам.",
    "11. Как вы обеспечиваете качество данных на протяжении их жизненного цикла? Назовите одну проблему качества данных и способ ее решения.",
    "12. Расскажите о сложной проблеме, связанной с данными, с которой вы столкнулись: как вы ее поняли, решали и каков был результат/вывод?",
    "13. Назовите свою самую сильную сторону как специалиста в одной из следующих областей: Data Scientist, Data Engineer, Data Analyst, MLOps Engineer, Project Manager?",
    "14. Объясните концепцию feature engineering и приведите пример того, как это улучшило модель, над которой вы работали.",
    "15. Как вы подходите к валидации модели, особенно при работе с временными рядами или несбалансированными наборами данных?",
    "16. Опишите ваш опыт работы с фреймворками глубокого обучения (например, TensorFlow, PyTorch) и проект, в котором вы их применяли.",
    "17. Обсудите плюсы и минусы различных решений для хранения данных (например, реляционные БД, NoSQL, колоночные хранилища) для крупномасштабной аналитики.",
    "18. Как вы обеспечиваете безопасность данных и соответствие нормативным требованиям (например, GDPR, HIPAA) в конвейерах данных и системах хранения?",
    "19. Опишите сложный ETL/ELT конвейер, который вы спроектировали или значительно улучшили. Каковы были ключевые проблемы и как вы их решили?",
    "20. Расскажите о вашем процессе создания информативной визуализации данных или дашборда. Какие инструменты вы предпочитаете и почему?",
    "21. Как бы вы подошли к A/B тестированию для оценки влияния новой функции веб-сайта? Какие метрики вы бы отслеживали?",
    "22. Приведите пример того, как вы использовали SQL для решения сложной аналитической проблемы или извлечения критически важных бизнес-инсайтов.",
    "23. Объясните важность воспроизводимости в рабочих процессах машинного обучения и инструменты/практики, которые вы используете для ее достижения.",
    "24. Опишите ваш опыт работы с контейнеризацией (например, Docker) и оркестрацией (например, Kubernetes) при развертывании ML-моделей.",
    "25. Как вы отслеживаете производительность ML-моделей в производственной среде и решаете такие проблемы, как дрейф концепции или дрейф данных?",
    "26. Как вы приоритизируете задачи и управляете ресурсами в проекте с интенсивным использованием данных, с участием множества заинтересованных сторон и сжатыми сроками?",
    "27. Опишите ваш подход к управлению рисками в технологическом проекте. Приведите пример риска, который вы выявили и смягчили.",
    "28. Как вы способствуете эффективной коммуникации и сотрудничеству между техническими членами команды (например, дата-сайентистами, инженерами) и нетехническими бизнес-стейкхолдерами?",
    "29. Опишите ситуацию, когда вам пришлось быстро изучить новую технологию или методологию для завершения проекта. Как вы к этому подошли?",
    "30. Рассматривая пять ролей (Data Scientist, Data Engineer, Data Analyst, MLOps Engineer, Project Manager), если бы вам пришлось выбрать вторичную область интересов или экспертизы среди них, какой бы она была и почему?"
]

QUESTIONS_PART1_TEXT = (
        "Здравствуйте. Давайте начнем.\n"
        "Пожалуйста, ответьте на первую часть вопросов (1-15):\n" +
        "\n".join(ALL_QUESTIONS_LIST[:15])
)

QUESTIONS_PART2_TEXT = (
        "Спасибо за ваши ответы. Теперь, пожалуйста, ответьте на вторую часть вопросов (16-30):\n" +
        "\n".join(ALL_QUESTIONS_LIST[15:])
)


class ChannelState:
    def __init__(self):
        self.state = "waiting_for_first_contact"
        self.dialog_history_raw: List[Dict[str, str]] = [{"role": "system", "content": get_main_system_prompt()}]
        self.message_count_candidate = 0
        self.first_candidate_message_text: str | None = None

    def reset(self):
        self.state = "waiting_for_first_contact"
        self.dialog_history_raw = [{"role": "system", "content": get_main_system_prompt()}]
        self.message_count_candidate = 0
        self.first_candidate_message_text = None
        print(f"Channel state reset.")


def get_channel_state(chat_id: int):
    if chat_id not in channel_states:
        channel_states[chat_id] = ChannelState()
    return channel_states[chat_id]


@router.channel_post(Command(commands=["start"]))
async def cmd_start_handler(message: Message, bot: Bot, command: CommandObject = None):
    chat_id = message.chat.id
    state = get_channel_state(chat_id)
    state.reset()
    print(f"Channel {chat_id}: State reset by /start. Waiting for first contact.")


@router.channel_post(F.text)
async def handle_channel_message(message: Message, bot: Bot):
    if message.from_user and message.from_user.id == bot.id:
        return

    chat_id = message.chat.id
    state = get_channel_state(chat_id)
    print(f"Channel {chat_id}: Received text '{message.text[:70]}...'. Current state: {state.state}")

    if state.state == "finished":
        print(f"Channel {chat_id}: Interview is finished. Ignoring message: '{message.text[:50]}...'")
        return

    if state.state == "waiting_for_first_contact":
        await send_first_part_of_initial_questions(message, state, bot)
    elif state.state == "waiting_for_initial_answers_part1":
        await send_second_part_of_initial_questions(message, state, bot)
    elif state.state == "waiting_for_initial_answers_part2":
        await process_all_initial_answers_with_llm(message, state, bot)
    elif state.state == "interview_in_progress":
        await handle_interview_message(message, state, bot)


async def send_first_part_of_initial_questions(message: Message, state: ChannelState, bot: Bot):
    if not llm_s:
        await message.answer("Извините, сервис для обработки запросов временно недоступен. Попробуйте позже.")
        state.reset()
        print(f"Channel {message.chat.id}: LLM service unavailable. State reset.")
        return

    state.first_candidate_message_text = message.text.strip()
    state.message_count_candidate = 1

    state.dialog_history_raw = llm_s.add_message_to_raw_history(
        list(state.dialog_history_raw), "user", state.first_candidate_message_text
    )
    state.dialog_history_raw = llm_s.add_message_to_raw_history(
        state.dialog_history_raw, "assistant", QUESTIONS_PART1_TEXT
    )

    await message.answer(QUESTIONS_PART1_TEXT)
    state.state = "waiting_for_initial_answers_part1"
    print(
        f"Channel {message.chat.id}: First part of initial questions sent. State -> waiting_for_initial_answers_part1")


async def send_second_part_of_initial_questions(message: Message, state: ChannelState, bot: Bot):
    candidate_answers_part1 = message.text.strip()
    state.message_count_candidate += 1

    state.dialog_history_raw = llm_s.add_message_to_raw_history(
        list(state.dialog_history_raw), "user", candidate_answers_part1
    )
    state.dialog_history_raw = llm_s.add_message_to_raw_history(
        state.dialog_history_raw, "assistant", QUESTIONS_PART2_TEXT
    )

    await message.answer(QUESTIONS_PART2_TEXT)
    state.state = "waiting_for_initial_answers_part2"
    print(
        f"Channel {message.chat.id}: Second part of initial questions sent. State -> waiting_for_initial_answers_part2")


async def process_all_initial_answers_with_llm(message: Message, state: ChannelState, bot: Bot):
    candidate_answers_part2 = message.text.strip()
    state.message_count_candidate += 1

    if not llm_s:
        await message.answer(
            "Извините, сервис для обработки запросов (LLM) временно недоступен. Попробуйте отправить ваши ответы позже.")
        print(
            f"Channel {message.chat.id}: LLM service unavailable for processing part 2 answers. State remains 'waiting_for_initial_answers_part2'.")
        return

    history_for_llm_call_langchain = llm_s.history_to_langchain_format(state.dialog_history_raw)
    bot_response_text = await llm_s.get_llm_response(history_for_llm_call_langchain, user_input=candidate_answers_part2)
    print(f"Channel {message.chat.id}: LLM response (after all initial answers): '{bot_response_text[:100]}...'")

    state.dialog_history_raw = llm_s.add_message_to_raw_history(
        list(state.dialog_history_raw), "user", candidate_answers_part2
    )

    if bot_response_text and "ошибка" not in bot_response_text.lower():  # Basic check for LLM error string
        state.dialog_history_raw = llm_s.add_message_to_raw_history(
            state.dialog_history_raw, "assistant", bot_response_text
        )
        await message.answer(bot_response_text)

        verdict_found = check_for_verdict(bot_response_text, state, message.chat.id)
        if verdict_found:
            print(
                f"Channel {message.chat.id}: Verdict found after initial Qs. State is '{state.state}'. Interview finished.")
            return
        else:
            state.state = "interview_in_progress"
            print(
                f"Channel {message.chat.id}: Initial answers processed, no verdict. State -> interview_in_progress.")
    else:
        error_msg_to_send = bot_response_text or "Произошла ошибка при обработке ваших ответов. Пожалуйста, попробуйте еще раз."  # Default message
        state.dialog_history_raw = llm_s.add_message_to_raw_history(
            state.dialog_history_raw, "assistant", error_msg_to_send  # Log LLM's error string or default
        )
        await message.answer(error_msg_to_send)  # Inform user
        print(
            f"Channel {message.chat.id}: LLM error or empty response for initial answers: '{error_msg_to_send}'. State remains 'waiting_for_initial_answers_part2'.")


async def handle_interview_message(message: Message, state: ChannelState, bot: Bot):
    user_text = message.text.strip()

    if not llm_s:
        await message.answer("Извините, сервис для обработки запросов временно недоступен. Попробуйте позже.")
        return

    state.message_count_candidate += 1

    history_for_llm_call_langchain = llm_s.history_to_langchain_format(state.dialog_history_raw)
    llm_intended_response = await llm_s.get_llm_response(history_for_llm_call_langchain, user_input=user_text)
    print(f"Channel {message.chat.id}: LLM response (interview processing): '{llm_intended_response[:100]}...'")

    state.dialog_history_raw = llm_s.add_message_to_raw_history(
        list(state.dialog_history_raw), "user", user_text
    )

    if llm_intended_response and "ошибка" not in llm_intended_response.lower():  # Basic check for LLM error string
        state.dialog_history_raw = llm_s.add_message_to_raw_history(
            state.dialog_history_raw, "assistant", llm_intended_response
        )
        await message.answer(llm_intended_response)

        verdict_found = check_for_verdict(llm_intended_response, state, message.chat.id)
        if verdict_found:
            print(f"Channel {message.chat.id}: Verdict found. State is '{state.state}'. Interview finished.")
            return

        print(f"Channel {message.chat.id}: Interview message processed, no verdict. State: {state.state}.")
    else:
        error_msg_to_send = llm_intended_response or "Произошла ошибка при генерации ответа. Попробуйте ответить еще раз."  # Default message
        state.dialog_history_raw = llm_s.add_message_to_raw_history(
            state.dialog_history_raw, "assistant", error_msg_to_send  # Log LLM's error string or default
        )
        await message.answer(error_msg_to_send)  # Inform user
        print(
            f"Channel {message.chat.id}: LLM error/empty response in interview: '{error_msg_to_send}'. State: {state.state}.")


def check_for_verdict(response_text: str, state: 'ChannelState', chat_id: int) -> bool:
    match = re.search(r"\[(.*?)\]", response_text)
    ## print(f"--- check_for_verdict (debug) --- Input response: '{response_text[:150]}'")
    if match:
        extracted_content = match.group(1).strip()

        normalized_extracted_content = extracted_content.lower()

        normalized_available_positions = [pos.lower().strip() for pos in AVAILABLE_POSITIONS]
        normalized_incompetent_verdict = INCOMPETENT_VERDICT.lower().strip()

        if normalized_extracted_content in normalized_available_positions or \
                normalized_extracted_content == normalized_incompetent_verdict:
            print(
                f"Channel {chat_id}: Verdict '{extracted_content}' (via normalized match) found. Setting state to finished.")
            state.state = "finished"
            return True
        else:
            print(
                f"Channel {chat_id}: Content '{extracted_content}' (normalized: '{normalized_extracted_content}') in brackets NOT a recognized verdict. Available normalized: {normalized_available_positions}")
    else:
        print(f"Channel {chat_id}: No bracketed verdict found in response.")
    return False


@router.channel_post(~F.text)
async def handle_non_text_channel_post(message: Message, bot: Bot):
    if message.from_user and message.from_user.id == bot.id:
        return

    chat_id = message.chat.id
    state = get_channel_state(chat_id)

    if state.state == "finished":
        print(f"Channel {chat_id}: Interview finished, ignoring non-text message.")
        return

    await message.answer("Пожалуйста, отправляйте только текстовые сообщения в рамках собеседования.")