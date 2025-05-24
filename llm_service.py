# hr_llm_bot/llm_service.py
import logging
from typing import List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

from config import VLLM_API_BASE, VLLM_API_KEY, LLM_MODEL_NAME

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, api_base: str = VLLM_API_BASE, api_key: str = VLLM_API_KEY, model_name: str = LLM_MODEL_NAME):
        try:
            self.llm = ChatOpenAI(
                model=model_name,
                openai_api_base=api_base,
                openai_api_key=api_key,
                temperature=0.1,
                max_tokens=1024,
            )
            self.prompt_template = ChatPromptTemplate.from_messages(
                [
                    MessagesPlaceholder(variable_name="history"),
                    HumanMessage(content="{input}"),
                ]
            )
            self.chain = self.prompt_template | self.llm | StrOutputParser()
            logger.info(f"LLMService initialized with model: {model_name} at {api_base}")
        except Exception as e:
            logger.critical(f"Failed to initialize LLMService: {e}", exc_info=True)
            raise

    async def get_llm_response(self, history: List[BaseMessage], user_input: str) -> Optional[str]:
        if not self.llm:
            logger.error("LLM is not initialized.")
            return "Ошибка: LLM сервис не инициализирован."
        try:
            response_content = await self.chain.ainvoke({"history": history, "input": user_input})
            return response_content
        except Exception as e:
            logger.error(f"Error interacting with LLM: {e}", exc_info=True)
            return "Извините, произошла ошибка при обращении к моему \"мозговому центру\". Попробуйте позже."

    @staticmethod
    def construct_message(role: str, content: str) -> BaseMessage:
        if role == "system":
            return SystemMessage(content=content)
        elif role == "user":
            return HumanMessage(content=content)
        elif role == "assistant":
            return AIMessage(content=content)
        else:
            logger.warning(f"Unknown role for message construction: {role}")
            return HumanMessage(content=content) # Fallback

    @staticmethod
    def history_to_langchain_format(raw_history: List[dict]) -> List[BaseMessage]:
        """Преобразует 'сырую' историю в формат BaseMessage для Langchain."""
        lc_history = []
        for msg_data in raw_history:
            lc_history.append(LLMService.construct_message(msg_data["role"], msg_data["content"]))
        return lc_history

    @staticmethod
    def add_message_to_raw_history(raw_history: List[dict], role: str, content: str) -> List[dict]:
        """Добавляет сообщение в 'сырую' историю."""
        raw_history.append({"role": role, "content": content})
        return raw_history