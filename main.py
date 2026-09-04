import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN, LOG_FILE, LOG_LEVEL
from handlers import text_router, accounts_router, tariffs_router, instruction_router, help_router
from handlers.accounts import load_accounts_data, save_accounts_data, user_sessions
from handlers.text_message import load_mailing_data, save_mailing_data
from handlers.tariffs import check_expired_subscriptions, load_referral_data, save_referral_data
from utils.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

load_accounts_data()
load_mailing_data()
load_referral_data()
check_expired_subscriptions()

async def main():
    session = AiohttpSession(timeout=60)
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(text_router)
    dp.include_router(accounts_router)
    dp.include_router(tariffs_router)
    dp.include_router(instruction_router)
    dp.include_router(help_router)

    await start_scheduler(bot)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), polling_timeout=60)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    finally:
        await stop_scheduler()
        save_accounts_data()
        save_mailing_data()
        save_referral_data()
        for user_id, clients in user_sessions.items():
            for client in clients:
                await client.disconnect()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен.")