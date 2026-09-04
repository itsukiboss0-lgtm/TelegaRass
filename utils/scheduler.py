import asyncio
import logging
from datetime import datetime
from typing import Dict
from aiogram import Bot
from config import SCHEDULE_CHECK_INTERVAL

logger = logging.getLogger(__name__)

scheduled_tasks: Dict[int, dict] = {}
scheduler_task = None

async def check_schedules(bot: Bot):
    from handlers.text_message import user_mailing_settings, mailing_task
    now = datetime.now()
    for user_id, task in list(scheduled_tasks.items()):
        if not task.get("active", False):
            continue
        start_time = task.get("start_time")
        if start_time and now >= start_time:
            settings = user_mailing_settings.get(user_id, {})
            if not settings.get("is_active", False):
                logger.info(f"🚀 Запуск рассылки по расписанию для пользователя {user_id}")
                asyncio.create_task(mailing_task(user_id))
                settings["is_active"] = True
                user_mailing_settings[user_id] = settings
                task["active"] = False
                scheduled_tasks[user_id] = task

async def scheduler_loop(bot: Bot):
    while True:
        try:
            await check_schedules(bot)
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике: {e}")
        await asyncio.sleep(SCHEDULE_CHECK_INTERVAL)

async def start_scheduler(bot: Bot):
    global scheduler_task
    scheduler_task = asyncio.create_task(scheduler_loop(bot))
    logger.info("🔄 Планировщик запущен")

async def stop_scheduler():
    if scheduler_task:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        logger.info("⏹ Планировщик остановлен")

def schedule_mailing(user_id: int, start_time: datetime):
    scheduled_tasks[user_id] = {
        "start_time": start_time,
        "active": True
    }
    logger.info(f"📅 Запланирована рассылка для {user_id} на {start_time}")

def cancel_schedule(user_id: int):
    if user_id in scheduled_tasks:
        scheduled_tasks[user_id]["active"] = False
        logger.info(f"❌ Расписание отменено для {user_id}")