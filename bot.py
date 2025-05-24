# bot.py (основной файл запуска бота)
import asyncio
import logging # Рекомендуется оставить для отладки, даже если в других местах убрали

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage # или RedisStorage, если используете

# Убедитесь, что BOT_TOKEN импортируется корректно
# Если config.py находится в той же директории:
from config import BOT_TOKEN

# Импортируем router из вашего файла handlers.py
# Убедитесь, что в handlers.py ваш роутер называется 'router'
# и он является экземпляром aiogram.Router
from handlers import router as handlers_router

# Настройка логирования (хотя бы базового для отладки ошибок Aiogram)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

async def start_bot():
    logger.info("Starting bot...")

    if not BOT_TOKEN:
        logger.critical("FATAL: BOT_TOKEN is not set!")
        return

    # 1. Инициализация FSM хранилища
    # MemoryStorage подходит для разработки и тестов.
    # Для продакшена лучше использовать персистентное хранилище, например, Redis.
    storage = MemoryStorage()

    # 2. Инициализация бота
    bot = Bot(token=BOT_TOKEN)

    # 3. Инициализация Dispatcher С ПЕРЕДАЧЕЙ ХРАНИЛИЩА (storage)
    # Это КРАЙНЕ ВАЖНО для работы FSM и автоматической передачи FSMContext (state).
    dp = Dispatcher(storage=storage)

    # 4. Подключение роутера из handlers.py к Dispatcher
    # Все обработчики, объявленные в handlers_router, теперь будут частью dp.
    dp.include_router(handlers_router)

    # Опционально: удаление ожидающих обновлений при старте
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Bot polling started...")
    try:
        # Запуск опроса Telegram API
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"An error occurred during polling: {e}", exc_info=True)
    finally:
        await bot.session.close()
        logger.info("Bot polling finished.")

if __name__ == '__main__':
    try:
        asyncio.run(start_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user (Ctrl+C or SystemExit).")
    except Exception as e: # Ловим другие возможные ошибки на уровне asyncio.run
        logger.critical(f"Critical error at asyncio.run level: {e}", exc_info=True)