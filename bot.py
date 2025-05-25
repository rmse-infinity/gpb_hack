import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN

from handlers import router as handlers_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

async def start_bot():
    logger.info("Starting bot...")

    storage = MemoryStorage()

    bot = Bot(token=BOT_TOKEN)

    dp = Dispatcher(storage=storage)

    dp.include_router(handlers_router)

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