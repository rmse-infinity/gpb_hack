import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
VLLM_API_BASE = os.environ.get("VLLM_API_BASE")
VLLM_API_KEY = os.environ.get("VLLM_API_KEY")
LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "leon-se/gemma-3-27b-it-FP8-Dynamic")

# Доступные позиции и вердикт
AVAILABLE_POSITIONS = ["Data Scientist", "Data Engineer", "Data Analyst", "MLOps Engineer", "Project Manager"]
INCOMPETENT_VERDICT = "[Некомпетентный соискатель]"
MAX_MESSAGES_PER_SIDE = 10 # По 10 сообщений от кандидата

# Логирование
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# Проверка обязательных переменных
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")
if not VLLM_API_BASE:
    raise ValueError("VLLM_API_BASE не найден в переменных окружения!")