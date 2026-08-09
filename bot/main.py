import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from bot.config import load_config
from bot.database import Database
from bot.handlers import common, group_admin, standup
from bot.scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main():
    config = load_config()

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    db = Database(config.database_path)
    await db.connect()

    scheduler = await setup_scheduler(bot, db)

    dp["db"] = db
    dp["config"] = config
    dp["scheduler"] = scheduler

    dp.include_router(common.router)
    dp.include_router(group_admin.router)
    dp.include_router(standup.router)

    try:
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
