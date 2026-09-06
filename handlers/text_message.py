import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from telethon.errors import RPCError, FloodWaitError
from telethon.tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityCode,
    MessageEntityPre, MessageEntityTextUrl, MessageEntityUrl,
    MessageEntityEmail, MessageEntityMention, MessageEntityHashtag,
    MessageEntityCashtag, MessageEntityPhone, MessageEntityUnderline,
    MessageEntityStrike, MessageEntityBlockquote, MessageEntityCustomEmoji
)

from config import DATA_FILE, BOT_USERNAME, BOT_TOKEN
from states import TextMessageStates, MailingStates, GroupStates
from keyboards import (
    main_menu_kb, get_menu_text_kb, get_count_kb, get_buttons_count_kb,
    get_home_kb, get_example_kb, get_cancel_kb, get_mailing_panel_kb,
    get_autostop_kb, get_mention_kb, get_stats_kb, get_stats_main_kb,
    get_groups_kb, build_groups_inline, get_cycle_interval_kb,
    get_message_interval_kb, get_schedule_kb
)

import handlers.accounts as accounts_module
from handlers.tariffs import is_subscription_active
from utils.scheduler import schedule_mailing, cancel_schedule

logger = logging.getLogger(__name__)
router = Router()
bot = Bot(token=BOT_TOKEN)

user_mailing_settings = {}
user_mailing_stats = {}
user_mailing_tasks = {}
temp_groups_data = {}
user_sent_messages = {}

def save_mailing_data():
    data = {
        "user_mailing_settings": user_mailing_settings,
        "user_mailing_stats": user_mailing_stats,
        "user_sent_messages": user_sent_messages
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

def load_mailing_data():
    global user_mailing_settings, user_mailing_stats, user_sent_messages
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            user_mailing_settings = data.get("user_mailing_settings", {})
            user_mailing_stats = data.get("user_mailing_stats", {})
            user_sent_messages = data.get("user_sent_messages", {})
    else:
        user_mailing_settings = {}
        user_mailing_stats = {}
        user_sent_messages = {}

def format_time(seconds: int) -> str:
    if seconds < 0:
        seconds = 0
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

def get_remaining_time(user_id: int) -> str:
    settings = user_mailing_settings.get(user_id, {})
    stats = user_mailing_stats.get(user_id, {})
    if not settings.get("is_active", False):
        return ""

    now = datetime.now()
    cycle_interval_min = settings.get("cycle_interval", 5)
    cycle_interval_sec = cycle_interval_min * 60

    cycle_end = stats.get("cycle_end_time")
    if cycle_end:
        try:
            end_dt = datetime.fromisoformat(cycle_end)
            next_start = end_dt + timedelta(seconds=cycle_interval_sec)
            remaining = (next_start - now).total_seconds()
            if remaining > 0:
                return f"⏳ До следующего цикла: {format_time(int(remaining))}"
            else:
                return "🔄 Следующий цикл вот-вот начнётся"
        except:
            pass
    start_time = settings.get("start_time")
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time) if isinstance(start_time, str) else start_time
            return f"⏳ Работает с {start_dt.strftime('%H:%M')}, следующий цикл после паузы"
        except:
            pass
    return ""

def get_panel_text(user_id: int) -> str:
    accounts = accounts_module.user_accounts.get(user_id, [])
    profile_info = "Не добавлен"
    if accounts:
        acc = accounts[0]
        profile_info = f"{acc.get('first_name', '')} {acc.get('last_name', '')} (@{acc.get('username', 'нет')})"
    settings = user_mailing_settings.get(user_id, {})
    msg_type = settings.get("message_type") or "Не настроено"
    groups = settings.get("groups_count", 0)
    interval_between_msgs = settings.get("interval", 5)
    cycle_interval = settings.get("cycle_interval", 5)
    auto_stop = settings.get("auto_stop_time")
    if auto_stop is None:
        auto_stop_str = "♾ Бесконечно"
    else:
        hours = auto_stop.total_seconds() // 3600
        auto_stop_str = f"{int(hours)} ч."
    mention = "Вкл" if settings.get("mention_enabled", False) else "Выкл"
    status = "✅ Активно" if settings.get("is_active", False) else "⏸ Неактивно"
    remaining = get_remaining_time(user_id)
    if remaining:
        remaining = "\n" + remaining

    text = (
        "📨 <b>Панель управления</b>\n\n"
        f"👤 <i>Профиль:</i> {profile_info}\n"
        f"📊 <i>Статус:</i> {status}\n"
        f"📝 <i>Тип сообщения:</i> {msg_type}\n"
        f"👥 <i>Группы:</i> {groups} (выбрано)\n"
        f"⏱ <i>Пауза между сообщениями:</i> {interval_between_msgs} сек.\n"
        f"🔄 <i>Интервал между циклами:</i> {cycle_interval} мин.\n"
        f"⏹ <i>Авто-стоп:</i> {auto_stop_str}\n"
        f"🔔 <i>Упоминание:</i> {mention}"
        f"{remaining}"
    )
    return text

def get_stats_text(user_id: int) -> str:
    stats = user_mailing_stats.get(user_id, {})
    if not stats or stats.get("status") == "Остановлена" and stats.get("sent_total", 0) == 0:
        return None
    remaining = get_remaining_time(user_id)
    if remaining:
        remaining = "\n" + remaining
    text = (
        "📊 <b>Статистика</b>\n\n"
        f"📌 <i>Статус:</i> {stats.get('status', 'Неизвестно')}\n"
        f"📈 <i>Отправлено сегодня:</i> {stats.get('sent_today', 0)}\n"
        f"📦 <i>Отправлено всего:</i> {stats.get('sent_total', 0)}\n"
        f"🔄 <i>Текущий цикл:</i> {stats.get('current_cycle', 0)}\n"
        f"✅ <i>Завершённые циклы:</i> {stats.get('completed_cycles', 0)}\n"
        f"👥 <i>Выбранные группы:</i> {stats.get('selected_groups', 0)}\n"
        f"⏳ <i>Готово к отправке:</i> {stats.get('ready_to_send', 0)}\n"
        f"⏱ <i>Пауза между сообщениями:</i> {stats.get('time_between_messages', 5)} сек.\n"
        f"🔄 <i>Интервал между циклами:</i> {stats.get('time_between_cycles', 5)} мин.\n"
        f"📅 <i>Последний цикл начат:</i> {stats.get('last_cycle_start') or '—'}"
        f"{remaining}"
    )
    return text

def get_signature(user_id: int) -> str:
    if is_subscription_active(user_id):
        return ""
    else:
        return f"\n\nPa$$ыLka 4epe3 - @{BOT_USERNAME}"

def extract_message_data(message: Message) -> dict:
    data = {}
    if message.html_text:
        data["text"] = message.html_text
    elif message.text:
        data["text"] = message.text
    else:
        data["text"] = ""

    if message.entities:
        data["entities"] = message.entities
    else:
        data["entities"] = []

    if message.photo:
        data["media"] = message.photo[-1].file_id
        data["media_type"] = "photo"
    elif message.video:
        data["media"] = message.video.file_id
        data["media_type"] = "video"
    elif message.document:
        data["media"] = message.document.file_id
        data["media_type"] = "document"
    elif message.audio:
        data["media"] = message.audio.file_id
        data["media_type"] = "audio"
    elif message.voice:
        data["media"] = message.voice.file_id
        data["media_type"] = "voice"
    elif message.animation:
        data["media"] = message.animation.file_id
        data["media_type"] = "animation"
    elif message.sticker:
        data["media"] = message.sticker.file_id
        data["media_type"] = "sticker"
    else:
        data["media"] = None
        data["media_type"] = None
    data["buttons"] = []
    return data

def convert_entities(entities, text: str):
    result = []
    for ent in entities:
        offset = ent.offset
        length = ent.length
        if ent.type == "bold":
            result.append(MessageEntityBold(offset=offset, length=length))
        elif ent.type == "italic":
            result.append(MessageEntityItalic(offset=offset, length=length))
        elif ent.type == "code":
            result.append(MessageEntityCode(offset=offset, length=length))
        elif ent.type == "pre":
            result.append(MessageEntityPre(offset=offset, length=length, language=ent.language or ""))
        elif ent.type == "text_link":
            result.append(MessageEntityTextUrl(offset=offset, length=length, url=ent.url))
        elif ent.type == "url":
            result.append(MessageEntityUrl(offset=offset, length=length))
        elif ent.type == "email":
            result.append(MessageEntityEmail(offset=offset, length=length))
        elif ent.type == "mention":
            result.append(MessageEntityMention(offset=offset, length=length))
        elif ent.type == "hashtag":
            result.append(MessageEntityHashtag(offset=offset, length=length))
        elif ent.type == "cashtag":
            result.append(MessageEntityCashtag(offset=offset, length=length))
        elif ent.type == "phone":
            result.append(MessageEntityPhone(offset=offset, length=length))
        elif ent.type == "underline":
            result.append(MessageEntityUnderline(offset=offset, length=length))
        elif ent.type == "strikethrough":
            result.append(MessageEntityStrike(offset=offset, length=length))
        elif ent.type == "blockquote":
            result.append(MessageEntityBlockquote(offset=offset, length=length))
        elif ent.type == "custom_emoji":
            result.append(MessageEntityCustomEmoji(offset=offset, length=length, document_id=ent.custom_emoji_id))
    return result

async def send_message_to_group(client, group_entity, message_data: dict, signature: str):
    try:
        text = message_data.get("text", "")
        if text and signature:
            text += signature

        media_type = message_data.get("media_type")
        media_id = message_data.get("media")

        if media_id and media_type:
            file = await bot.get_file(media_id)
            file_bytes = await bot.download_file(file.file_path)
            temp_file = f"temp_{datetime.now().timestamp()}.jpg"
            with open(temp_file, "wb") as f:
                f.write(file_bytes)
            await client.send_file(
                entity=group_entity,
                file=temp_file,
                caption=text if text else None,
                parse_mode='html'
            )
            if os.path.exists(temp_file):
                os.remove(temp_file)
        else:
            entities = message_data.get("entities")
            if entities:
                telethon_entities = convert_entities(entities, text)
                await client.send_message(
                    entity=group_entity,
                    message=text,
                    entities=telethon_entities
                )
            else:
                await client.send_message(
                    entity=group_entity,
                    message=text,
                    parse_mode='html'
                )
        return True, None
    except FloodWaitError as e:
        return False, f"FloodWait: {e.seconds} сек."
    except RPCError as e:
        return False, str(e)
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        return False, str(e)

async def mailing_task(user_id: int):
    settings = user_mailing_settings.get(user_id, {})
    stats = user_mailing_stats.get(user_id, {})
    signature = get_signature(user_id)
    sessions = accounts_module.user_sessions.get(user_id, [])
    if not sessions:
        stats["status"] = "Нет активной сессии"
        user_mailing_stats[user_id] = stats
        save_mailing_data()
        return
    client = sessions[0]
    msg_data = user_sent_messages.get(user_id, {})
    if not msg_data:
        stats["status"] = "Нет сохранённого сообщения"
        user_mailing_stats[user_id] = stats
        save_mailing_data()
        return

    is_multiple = isinstance(msg_data, list)
    if is_multiple and not msg_data:
        stats["status"] = "Пустой список сообщений"
        user_mailing_stats[user_id] = stats
        save_mailing_data()
        return
    if not is_multiple:
        messages = [msg_data]
    else:
        messages = msg_data

    group_ids = settings.get("groups_list", [])
    if not group_ids:
        stats["status"] = "Не выбраны группы"
        user_mailing_stats[user_id] = stats
        save_mailing_data()
        return

    group_entities = []
    for g in group_ids:
        try:
            entity = await client.get_entity(g['id'])
            group_entities.append(entity)
        except Exception as e:
            logger.error(f"Не удалось получить сущность группы {g['id']}: {e}")
    if not group_entities:
        stats["status"] = "Не удалось получить ни одной группы"
        user_mailing_stats[user_id] = stats
        save_mailing_data()
        return

    interval = settings.get("interval", 5)
    cycle_interval = settings.get("cycle_interval", 5)
    msg_index = 0

    try:
        while settings.get("is_active", False):
            if settings.get("stop_time") and datetime.now() >= settings["stop_time"]:
                settings["is_active"] = False
                stats["status"] = "Остановлена по таймеру"
                break

            stats["cycle_start_time"] = datetime.now().isoformat()
            stats["cycle_end_time"] = None
            for group_entity in group_entities:
                if not settings.get("is_active", False):
                    break
                current_msg = messages[msg_index % len(messages)]
                msg_index += 1

                success, error = await send_message_to_group(client, group_entity, current_msg, signature)
                if success:
                    stats["sent_today"] += 1
                    stats["sent_total"] += 1
                    stats["current_cycle"] += 1
                    stats["last_cycle_start"] = datetime.now().isoformat()
                else:
                    logger.warning(f"Ошибка отправки в группу {group_entity.id}: {error}")
                await asyncio.sleep(interval)

            stats["completed_cycles"] += 1
            stats["current_cycle"] = 0
            stats["cycle_end_time"] = datetime.now().isoformat()
            user_mailing_stats[user_id] = stats
            save_mailing_data()

            if settings.get("is_active", False):
                await asyncio.sleep(cycle_interval * 60)

        if settings.get("is_active", False):
            settings["is_active"] = False
            stats["status"] = "Завершена"
        else:
            stats["status"] = "Остановлена пользователем"
    except asyncio.CancelledError:
        settings["is_active"] = False
        stats["status"] = "Остановлена пользователем"
        raise
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        stats["status"] = f"Ошибка: {str(e)}"
        settings["is_active"] = False
    finally:
        user_mailing_settings[user_id] = settings
        user_mailing_stats[user_id] = stats
        save_mailing_data()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split()
    if len(args) > 1:
        param = args[1]
        if param.startswith("ref_"):
            referrer_id_str = param.split("_")[1]
            if referrer_id_str.isdigit():
                referrer_id = int(referrer_id_str)
                user_id = message.from_user.id
                if referrer_id != user_id:
                    from handlers.tariffs import add_referral
                    success = add_referral(referrer_id, user_id)
                    if success:
                        await message.answer("🎉 Вы приглашены другом! Ему начислено 12 часов PRO. Спасибо!")
                    else:
                        await message.answer("Вы уже приглашены или это ваш собственный реферал.")
    await message.answer(
        "🌟 Добро пожаловать в <b>Mail Pulse</b>!\n"
        "Выберите нужный раздел в главном меню 👇",
        reply_markup=main_menu_kb
    )

@router.message(F.text == "🚀 Авто рассылка")
async def auto_mailing_panel(message: Message, state: FSMContext):
    await state.set_state(MailingStates.panel)
    user_id = message.from_user.id
    if user_id not in user_mailing_settings:
        user_mailing_settings[user_id] = {
            "message_type": None,
            "groups_count": 0,
            "groups_list": [],
            "interval": 5,
            "cycle_interval": 5,
            "auto_stop_time": None,
            "mention_enabled": False,
            "is_active": False,
            "start_time": None,
            "stop_time": None,
        }
    if user_id not in user_mailing_stats:
        user_mailing_stats[user_id] = {
            "status": "Остановлена",
            "sent_today": 0,
            "sent_total": 0,
            "current_cycle": 0,
            "completed_cycles": 0,
            "selected_groups": 0,
            "ready_to_send": 0,
            "time_between_messages": 5,
            "time_between_cycles": 5,
            "last_cycle_start": None,
            "cycle_start_time": None,
            "cycle_end_time": None,
        }
    panel_text = get_panel_text(user_id)
    is_active = user_mailing_settings[user_id].get("is_active", False)
    await message.answer(panel_text, reply_markup=get_mailing_panel_kb(is_active))

@router.callback_query(MailingStates.panel, lambda c: c.data == "refresh_panel")
async def refresh_panel_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    panel_text = get_panel_text(user_id)
    is_active = user_mailing_settings[user_id].get("is_active", False)
    await callback.message.edit_text(panel_text, reply_markup=get_mailing_panel_kb(is_active))

@router.callback_query(MailingStates.panel, lambda c: c.data == "start_mailing")
async def start_mailing_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    settings = user_mailing_settings.get(user_id, {})
    stats = user_mailing_stats.get(user_id, {})

    if not accounts_module.user_accounts.get(user_id):
        await callback.message.edit_text("❌ Сначала добавьте профиль в разделе «Профили».", reply_markup=get_mailing_panel_kb(False))
        return
    if not settings.get("message_type"):
        await callback.message.edit_text("❌ Настройте тип сообщения в разделе «Текст сообщения».", reply_markup=get_mailing_panel_kb(False))
        return
    if settings.get("groups_count", 0) < 1:
        await callback.message.edit_text("❌ Добавьте хотя бы одну группу в разделе «Настройка групп».", reply_markup=get_mailing_panel_kb(False))
        return
    if settings.get("is_active", False):
        await callback.message.edit_text("⚠️ Рассылка уже запущена.", reply_markup=get_mailing_panel_kb(True))
        return
    if user_id not in user_sent_messages:
        await callback.message.edit_text("❌ Не найдено сохранённое сообщение. Настройте его в разделе «Текст сообщения».", reply_markup=get_mailing_panel_kb(False))
        return

    stats["status"] = "Идёт отправка"
    stats["sent_today"] = 0
    stats["sent_total"] = 0
    stats["current_cycle"] = 0
    stats["completed_cycles"] = 0
    stats["selected_groups"] = settings.get("groups_count", 0)
    stats["ready_to_send"] = settings.get("groups_count", 0)
    stats["time_between_messages"] = settings.get("interval", 5)
    stats["time_between_cycles"] = settings.get("cycle_interval", 5)
    stats["last_cycle_start"] = None
    stats["cycle_start_time"] = None
    stats["cycle_end_time"] = None
    settings["is_active"] = True
    settings["start_time"] = datetime.now().isoformat()
    if settings.get("auto_stop_time"):
        settings["stop_time"] = (datetime.now() + settings["auto_stop_time"]).isoformat()
    else:
        settings["stop_time"] = None

    user_mailing_settings[user_id] = settings
    user_mailing_stats[user_id] = stats
    save_mailing_data()

    task = asyncio.create_task(mailing_task(user_id))
    user_mailing_tasks[user_id] = task

    await callback.message.edit_text(
        "🚀 Рассылка запущена!\nДля просмотра статистики нажмите «📊 Статистика».",
        reply_markup=get_mailing_panel_kb(True)
    )

@router.callback_query(MailingStates.panel, lambda c: c.data == "stop_mailing")
async def stop_mailing_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    settings = user_mailing_settings.get(user_id, {})
    stats = user_mailing_stats.get(user_id, {})

    if not settings.get("is_active", False):
        await callback.message.edit_text("⚠️ Рассылка уже остановлена.", reply_markup=get_mailing_panel_kb(False))
        return

    task = user_mailing_tasks.get(user_id)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    if user_id in user_mailing_tasks:
        del user_mailing_tasks[user_id]

    settings["is_active"] = False
    stats["status"] = "Остановлена пользователем"
    user_mailing_settings[user_id] = settings
    user_mailing_stats[user_id] = stats
    save_mailing_data()

    await callback.message.edit_text(
        "⏹️ Рассылка остановлена.",
        reply_markup=get_mailing_panel_kb(False)
    )
    panel_text = get_panel_text(user_id)
    await callback.message.answer(panel_text, reply_markup=get_mailing_panel_kb(False))

@router.callback_query(MailingStates.panel, lambda c: c.data == "show_stats")
async def show_statistics_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    stats_text = get_stats_text(user_id)
    if stats_text is None:
        await callback.message.edit_text(
            "📊 Статистика доступна только после запуска рассылки.",
            reply_markup=get_mailing_panel_kb(user_mailing_settings[user_id].get("is_active", False))
        )
        return
    await state.set_state(MailingStates.statistics_view)
    await callback.message.edit_text(stats_text, reply_markup=get_stats_kb())

@router.callback_query(MailingStates.statistics_view, lambda c: c.data == "refresh_stats")
async def refresh_stats_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await show_statistics_callback(callback, state)

@router.callback_query(MailingStates.panel, lambda c: c.data == "autostop_menu")
async def autostop_menu_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(MailingStates.autostop_setting)
    settings = user_mailing_settings.get(callback.from_user.id, {})
    current = settings.get("auto_stop_time")
    if current is None:
        current_str = "♾ Бесконечно"
    else:
        if isinstance(current, timedelta):
            hours = current.total_seconds() // 3600
            current_str = f"{int(hours)} ч."
        else:
            current_str = "♾ Бесконечно"
    await callback.message.edit_text(
        f"⏱ <b>Авто-стоп</b>\n"
        f"Автоматическая рассылка остановится через заданное время после запуска.\n"
        f"⏱ Текущее: {current_str}\n\n"
        "Выберите время 👇",
        reply_markup=get_autostop_kb()
    )

@router.callback_query(MailingStates.autostop_setting, lambda c: c.data.startswith("autostop_"))
async def set_autostop_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = callback.data
    if data == "autostop_infinite":
        delta = None
        text = "♾ Бесконечно"
    else:
        hours = int(data.split("_")[1])
        delta = timedelta(hours=hours)
        text = f"{hours} час(ов)"
    user_id = callback.from_user.id
    settings = user_mailing_settings.get(user_id, {})
    settings["auto_stop_time"] = delta
    user_mailing_settings[user_id] = settings
    save_mailing_data()
    await state.set_state(MailingStates.panel)
    panel_text = get_panel_text(user_id)
    is_active = settings.get("is_active", False)
    await callback.message.edit_text(
        f"✅ Авто-стоп установлен: {text}",
        reply_markup=get_mailing_panel_kb(is_active)
    )
    await callback.message.answer(panel_text, reply_markup=get_mailing_panel_kb(is_active))

@router.callback_query(MailingStates.panel, lambda c: c.data == "mention_menu")
async def mention_menu_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(MailingStates.mention_setting)
    settings = user_mailing_settings.get(callback.from_user.id, {})
    status = "Включены" if settings.get("mention_enabled", False) else "Выключены"
    await callback.message.edit_text(
        f"🔔 <b>Упоминания</b>\n\n"
        f"В конец сообщения через невидимые символы добавляется reply/упоминание участников.\n"
        f"(Осторожно, возможен риск спамблока)\n\n"
        f"Текущее состояние: {status}\n\n"
        "Выберите действие 👇",
        reply_markup=get_mention_kb()
    )

@router.callback_query(MailingStates.mention_setting, lambda c: c.data in ["mention_on", "mention_off"])
async def set_mention_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    settings = user_mailing_settings.get(user_id, {})
    settings["mention_enabled"] = (callback.data == "mention_on")
    user_mailing_settings[user_id] = settings
    save_mailing_data()
    await state.set_state(MailingStates.panel)
    panel_text = get_panel_text(user_id)
    is_active = settings.get("is_active", False)
    await callback.message.edit_text(
        f"✅ Упоминания {'включены' if settings['mention_enabled'] else 'выключены'}.",
        reply_markup=get_mailing_panel_kb(is_active)
    )
    await callback.message.answer(panel_text, reply_markup=get_mailing_panel_kb(is_active))

@router.callback_query(MailingStates.panel, lambda c: c.data == "schedule_mailing")
async def schedule_menu_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📅 <b>Запланировать рассылку</b>\n\n"
        "Выберите время запуска 👇",
        reply_markup=get_schedule_kb()
    )

@router.callback_query(lambda c: c.data.startswith("schedule_"))
async def schedule_set_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    now = datetime.now()
    if callback.data == "schedule_tomorrow_10":
        start_time = now.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
    elif callback.data == "schedule_tomorrow_15":
        start_time = now.replace(hour=15, minute=0, second=0, microsecond=0) + timedelta(days=1)
    elif callback.data == "schedule_dayafter_10":
        start_time = now.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=2)
    elif callback.data == "schedule_custom":
        await state.set_state(MailingStates.schedule_custom_time)
        await callback.message.edit_text(
            "⏳ Введите дату и время в формате <b>YYYY-MM-DD HH:MM</b>\n"
            "Например: 2025-12-31 18:00"
        )
        return
    else:
        await callback.message.edit_text("❌ Неверный выбор.")
        return
    schedule_mailing(user_id, start_time)
    await callback.message.edit_text(
        f"✅ Рассылка запланирована на {start_time.strftime('%d.%m.%Y %H:%M')}",
        reply_markup=get_mailing_panel_kb(False)
    )

@router.message(MailingStates.schedule_custom_time)
async def schedule_custom_time_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        dt = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте YYYY-MM-DD HH:MM")
        return
    if dt < datetime.now():
        await message.answer("❌ Указанное время уже прошло. Укажите будущее время.")
        return
    schedule_mailing(user_id, dt)
    await state.set_state(MailingStates.panel)
    panel_text = get_panel_text(user_id)
    await message.answer(f"✅ Рассылка запланирована на {dt.strftime('%d.%m.%Y %H:%M')}", reply_markup=get_mailing_panel_kb(False))
    await message.answer(panel_text, reply_markup=get_mailing_panel_kb(False))

@router.callback_query(lambda c: c.data == "back_to_panel")
async def back_to_panel_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    await state.set_state(MailingStates.panel)
    panel_text = get_panel_text(user_id)
    is_active = user_mailing_settings[user_id].get("is_active", False)
    await callback.message.edit_text(panel_text, reply_markup=get_mailing_panel_kb(is_active))

# ====== ТЕКСТ СООБЩЕНИЯ ======
@router.message(F.text == "📝 Текст сообщения")
async def cmd_text_message(message: Message, state: FSMContext):
    await state.set_state(TextMessageStates.choosing_type)
    await message.answer(
        "📝 <b>Настройка сообщения</b>\n\n"
        "Текущий тип: не выбран\n\n"
        "Выберите тип сообщения 👇",
        reply_markup=get_menu_text_kb()
    )

@router.callback_query(TextMessageStates.choosing_type, lambda c: c.data.startswith("type_"))
async def choose_type_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    choice = callback.data.split("_")[1]
    if choice == "ordinary":
        await state.set_state(TextMessageStates.waiting_ordinary)
        await state.update_data(mode="ordinary")
        await callback.message.edit_text(
            "📩 Отправьте сообщение\n\n"
            "Поддерживается:\n"
            "• Текст с форматированием (<b>жирный</b>, <i>курсив</i>, <code>код</code>, <blockquote>цитата</blockquote>)\n"
            "• Фото, видео, документы, голосовые\n"
            "• Пересылка (кроме премиум-эмодзи)",
            reply_markup=get_cancel_kb("back_to_choosing_type")
        )
    elif choice == "multiple":
        await state.set_state(TextMessageStates.waiting_count)
        await state.update_data(mode="multiple")
        await callback.message.edit_text(
            "📨 <b>Разные сообщения</b>\n\n"
            "Сколько вариантов настроить? В каждом цикле отправляется по очереди.",
            reply_markup=get_count_kb()
        )
    elif choice == "buttons":
        await state.set_state(TextMessageStates.waiting_main_message)
        await state.update_data(mode="buttons")
        await callback.message.edit_text(
            "🔗 <b>Сообщение с кнопками</b>\n\n"
            "Отправьте основное сообщение (текст, фото, видео, голос).\n"
            "Форматирование поддерживается.\n\n"
            "⚠️ <i>Премиум-эмодзи и пересылка не работают</i>",
            reply_markup=get_cancel_kb("back_to_choosing_type")
        )

@router.callback_query(TextMessageStates.choosing_type, lambda c: c.data == "back_to_choosing_type")
async def back_to_choosing_type_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TextMessageStates.choosing_type)
    await callback.message.edit_text(
        "📝 <b>Настройка сообщения</b>\n\n"
        "Текущий тип: не выбран\n\n"
        "Выберите тип сообщения 👇",
        reply_markup=get_menu_text_kb()
    )

@router.message(TextMessageStates.waiting_ordinary)
async def save_ordinary_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    msg_data = extract_message_data(message)
    if not msg_data:
        await message.answer("❌ Не удалось распознать сообщение. Попробуйте снова.")
        return
    user_sent_messages[user_id] = msg_data
    if user_id not in user_mailing_settings:
        user_mailing_settings[user_id] = {}
    user_mailing_settings[user_id]["message_type"] = "Обычное"
    save_mailing_data()
    await message.answer(
        "✅ Сохранение №1 сохранено.\n\n"
        "Чтобы вернуться на главную, нажмите кнопку ниже.",
        reply_markup=get_home_kb()
    )
    await state.set_state(TextMessageStates.going_home)

@router.message(TextMessageStates.waiting_ordinary, F.text == "⬅️ Назад")
async def back_from_ordinary(message: Message, state: FSMContext):
    await state.set_state(TextMessageStates.choosing_type)
    await message.answer("Выберите тип сообщения 👇", reply_markup=get_menu_text_kb())

@router.callback_query(TextMessageStates.waiting_count, lambda c: c.data.startswith("count_"))
async def choose_count_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    count = int(callback.data.split("_")[1])
    await state.update_data(total=count, current_index=0, messages=[])
    await state.set_state(TextMessageStates.waiting_message_n)
    await callback.message.edit_text(
        f"Отправьте сообщение №1 (1/{count})\n\nПересылка, фото и всё остальное — принимается.",
        reply_markup=get_cancel_kb("back_to_count")
    )

@router.callback_query(TextMessageStates.waiting_count, lambda c: c.data == "back_to_count")
async def back_to_count_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TextMessageStates.choosing_type)
    await callback.message.edit_text(
        "📝 <b>Настройка сообщения</b>\n\n"
        "Текущий тип: не выбран\n\n"
        "Выберите тип сообщения 👇",
        reply_markup=get_menu_text_kb()
    )

@router.message(TextMessageStates.waiting_message_n)
async def save_multiple_message(message: Message, state: FSMContext):
    data = await state.get_data()
    idx = data.get("current_index", 0)
    total = data.get("total", 0)
    messages = data.get("messages", [])
    msg_data = extract_message_data(message)
    if not msg_data:
        await message.answer("❌ Не удалось распознать сообщение. Попробуйте снова.")
        return
    messages.append(msg_data)
    idx += 1
    await state.update_data(messages=messages, current_index=idx)
    if idx < total:
        await message.answer(
            f"Отправьте сообщение №{idx+1} ({idx+1}/{total})\n\nПересылка, фото и всё остальное — принимается.",
            reply_markup=get_cancel_kb("back_to_multiple")
        )
    else:
        user_id = message.from_user.id
        user_sent_messages[user_id] = messages
        if user_id not in user_mailing_settings:
            user_mailing_settings[user_id] = {}
        user_mailing_settings[user_id]["message_type"] = "Разные"
        save_mailing_data()
        await message.answer(
            f"✅ Сохранение №{idx} сохранено.\n\n"
            "Чтобы вернуться на главную, нажмите кнопку ниже.",
            reply_markup=get_home_kb()
        )
        await state.set_state(TextMessageStates.going_home)

@router.callback_query(TextMessageStates.waiting_message_n, lambda c: c.data == "back_to_multiple")
async def back_to_multiple_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(messages=[], current_index=0)
    await state.set_state(TextMessageStates.waiting_count)
    await callback.message.edit_text(
        "📨 <b>Разные сообщения</b>\n\n"
        "Сколько вариантов настроить? В каждом цикле отправляется по очереди.",
        reply_markup=get_count_kb()
    )

@router.message(TextMessageStates.waiting_main_message)
async def save_main_message(message: Message, state: FSMContext):
    msg_data = extract_message_data(message)
    if not msg_data:
        await message.answer("❌ Не удалось распознать сообщение. Попробуйте снова.")
        return
    await state.update_data(main_message=msg_data)
    await message.answer(
        "🔘 <b>Это ваша кнопка</b>\n\n"
        "Вот так вот она будет выглядеть под сообщением",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="ваша кнопка", url="https://t.me/your_bot")]
        ])
    )
    await message.answer(
        "Сколько кнопок настроить?\n(Премиум-эмодзи и пересылка не работают)",
        reply_markup=get_buttons_count_kb()
    )
    await state.set_state(TextMessageStates.waiting_buttons_count)

@router.callback_query(TextMessageStates.waiting_main_message, lambda c: c.data == "back_to_main_message")
async def back_to_main_message_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TextMessageStates.choosing_type)
    await callback.message.edit_text(
        "📝 <b>Настройка сообщения</b>\n\n"
        "Текущий тип: не выбран\n\n"
        "Выберите тип сообщения 👇",
        reply_markup=get_menu_text_kb()
    )

@router.callback_query(TextMessageStates.waiting_buttons_count, lambda c: c.data.startswith("btncount_"))
async def choose_buttons_count_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    count = int(callback.data.split("_")[1])
    await state.update_data(buttons_total=count, button_index=0, buttons=[])
    await state.set_state(TextMessageStates.waiting_button_name)
    await ask_button_name(callback.message, state, 1)

async def ask_button_name(message: types.Message, state: FSMContext, num: int):
    await message.answer(
        f"Введите название кнопки №{num}\n\nНе более 64 символов.",
        reply_markup=get_cancel_kb("back_to_buttons_count")
    )

@router.message(TextMessageStates.waiting_button_name)
async def save_button_name(message: Message, state: FSMContext):
    if len(message.text) > 64:
        await message.answer("Название не должно превышать 64 символа. Попробуйте снова.")
        return
    await state.update_data(current_button_name=message.text)
    await state.set_state(TextMessageStates.waiting_button_url)
    data = await state.get_data()
    num = len(data.get("buttons", [])) + 1
    await message.answer(
        f"Ссылка для кнопки №{num}\n\nhttp://",
        reply_markup=get_cancel_kb("back_to_button_name")
    )

@router.message(TextMessageStates.waiting_button_url)
async def save_button_url(message: Message, state: FSMContext):
    url = message.text.strip()
    if not url.startswith(("http://", "https://")):
        await message.answer("Ссылка должна начинаться с http:// или https://. Попробуйте снова.")
        return
    data = await state.get_data()
    name = data.get("current_button_name")
    buttons = data.get("buttons", [])
    buttons.append((name, url))
    await state.update_data(buttons=buttons)
    total = data.get("buttons_total", 0)
    if len(buttons) < total:
        await state.set_state(TextMessageStates.waiting_button_name)
        await ask_button_name(message, state, len(buttons) + 1)
    else:
        user_id = message.from_user.id
        main_msg = await state.get_value("main_message")
        if main_msg:
            main_msg["buttons"] = buttons
            user_sent_messages[user_id] = main_msg
        if user_id not in user_mailing_settings:
            user_mailing_settings[user_id] = {}
        user_mailing_settings[user_id]["message_type"] = "С кнопками"
        save_mailing_data()
        await state.set_state(TextMessageStates.showing_example)
        await message.answer(
            "✅ Сообщение с кнопками сохранено.\n\n"
            "Чтобы посмотреть как выглядит сообщение или вернуться в главное меню нажмите на кнопки ниже.",
            reply_markup=get_example_kb()
        )

@router.callback_query(TextMessageStates.waiting_button_name, lambda c: c.data == "back_to_button_name")
async def back_to_button_name_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TextMessageStates.waiting_buttons_count)
    await callback.message.edit_text(
        "Сколько кнопок настроить?\n(Премиум-эмодзи и пересылка не работают)",
        reply_markup=get_buttons_count_kb()
    )

@router.callback_query(TextMessageStates.waiting_buttons_count, lambda c: c.data == "back_to_buttons_count")
async def back_to_buttons_count_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TextMessageStates.waiting_main_message)
    await callback.message.edit_text(
        "Отправьте основное сообщение",
        reply_markup=get_cancel_kb("back_to_main_message")
    )

@router.callback_query(TextMessageStates.showing_example, lambda c: c.data == "show_example")
async def show_example_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    msg_data = user_sent_messages.get(user_id, {})
    if not msg_data:
        await callback.message.edit_text("Основное сообщение не найдено.")
        return
    text = msg_data.get("text", "")
    buttons = msg_data.get("buttons", [])
    if buttons:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=name, url=url)] for name, url in buttons
        ])
    else:
        kb = None
    await callback.message.answer(
        text if text else "📎 Пример сообщения с кнопками",
        reply_markup=kb
    )

@router.callback_query(lambda c: c.data == "go_home")
async def go_home_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("🏠 Возврат в главное меню.")
    await callback.message.answer("Выберите раздел 👇", reply_markup=main_menu_kb)

# ====== НАСТРОЙКА ГРУПП ======
@router.message(F.text == "👥 Настройка групп")
async def groups_menu(message: Message, state: FSMContext):
    await state.set_state(GroupStates.main)
    user_id = message.from_user.id
    settings = user_mailing_settings.get(user_id, {})
    if not settings.get("groups_list"):
        settings["groups_list"] = []
        user_mailing_settings[user_id] = settings
        save_mailing_data()
    selected_groups = settings.get("groups_list", [])
    if selected_groups:
        groups_text = "\n".join([f"• {g.get('title', 'Без названия')} 👥 {g.get('participants_count', 0)}" for g in selected_groups])
    else:
        groups_text = "Не настроено"
    await message.answer(
        f"👥 <b>Настройка групп</b>\n\n"
        f"📋 Выбранные группы:\n{groups_text}\n\n"
        "Выберите действие 👇",
        reply_markup=get_groups_kb()
    )

@router.callback_query(GroupStates.main, lambda c: c.data == "groups_list")
async def groups_list_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    settings = user_mailing_settings.get(user_id, {})
    selected_groups = settings.get("groups_list", [])

    if not selected_groups:
        await callback.message.edit_text("📭 Вы пока не выбрали ни одной группы.", reply_markup=get_groups_kb())
        return

    buttons = []
    for g in selected_groups:
        title = g.get('title', 'Без названия')
        participants = g.get('participants_count', 0)
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {title} ({participants})",
                callback_data=f"remove_group_{g['id']}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_groups_menu")])

    await callback.message.edit_text(
        "📋 <b>Ваши выбранные группы:</b>\n\n"
        "Нажмите на группу, чтобы удалить её из списка.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(lambda c: c.data.startswith('remove_group_'))
async def remove_group_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    group_id = int(callback.data.split('_')[2])

    settings = user_mailing_settings.get(user_id, {})
    groups = settings.get("groups_list", [])

    group_to_remove = None
    for g in groups:
        if g['id'] == group_id:
            group_to_remove = g
            break

    if not group_to_remove:
        await callback.message.edit_text("❌ Группа не найдена.", reply_markup=get_groups_kb())
        return

    groups.remove(group_to_remove)
    settings["groups_list"] = groups
    settings["groups_count"] = len(groups)
    user_mailing_settings[user_id] = settings
    save_mailing_data()

    await callback.message.edit_text(
        f"✅ Группа «{group_to_remove.get('title', 'Без названия')}» удалена.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Показать обновлённый список", callback_data="groups_list")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_groups_menu")]
        ])
    )

@router.callback_query(lambda c: c.data == "back_to_groups_menu")
async def back_to_groups_menu_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    settings = user_mailing_settings.get(user_id, {})
    selected_groups = settings.get("groups_list", [])
    if selected_groups:
        groups_text = "\n".join([f"• {g.get('title', 'Без названия')} 👥 {g.get('participants_count', 0)}" for g in selected_groups])
    else:
        groups_text = "Не настроено"

    await callback.message.edit_text(
        f"👥 <b>Настройка групп</b>\n\n"
        f"📋 Выбранные группы:\n{groups_text}\n\n"
        "Выберите действие 👇",
        reply_markup=get_groups_kb()
    )

@router.callback_query(GroupStates.main, lambda c: c.data == "groups_add")
async def groups_add_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    sessions = accounts_module.user_sessions.get(user_id, [])
    if not sessions:
        await callback.message.edit_text("❌ Сначала добавьте профиль в разделе «Профили».", reply_markup=get_groups_kb())
        return
    client = sessions[0]
    try:
        dialogs = await client.get_dialogs()
        groups = []
        for dialog in dialogs:
            entity = dialog.entity
            if isinstance(entity, (Channel, Chat)):
                is_group = getattr(entity, 'megagroup', False) or getattr(entity, 'chat', False)
                is_broadcast = getattr(entity, 'broadcast', False)
                if is_group and not is_broadcast:
                    title = getattr(entity, 'title', 'Без названия')
                    participants_count = getattr(entity, 'participants_count', 0)
                    groups.append({
                        'id': entity.id,
                        'title': title,
                        'participants_count': participants_count
                    })
        if not groups:
            await callback.message.edit_text("📭 У вас нет групп (только каналы или пусто).", reply_markup=get_groups_kb())
            return
        temp_groups_data[user_id] = {'groups': groups, 'page': 0}
        await show_groups_page_callback(callback, state, user_id, 0)
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка при загрузке групп: {str(e)}\nПопробуйте позже.", reply_markup=get_groups_kb())

async def show_groups_page_callback(callback: CallbackQuery, state: FSMContext, user_id: int, page: int):
    data = temp_groups_data.get(user_id)
    if not data:
        await callback.message.edit_text("Сессия истекла. Начните заново.", reply_markup=get_groups_kb())
        return
    groups = data.get('groups', [])
    if not groups:
        await callback.message.edit_text("Нет доступных групп.", reply_markup=get_groups_kb())
        return
    kb = build_groups_inline(groups, page)
    data['page'] = page
    temp_groups_data[user_id] = data
    await callback.message.edit_text(
        "📋 <b>Выберите группы для добавления</b> (нажмите на название):\n\n"
        "Доступные группы (отображаются по 9):",
        reply_markup=kb
    )

@router.callback_query(lambda c: c.data.startswith('add_group_') or c.data.startswith('groups_page_') or c.data in ['save_groups', 'select_all_groups'])
async def handle_group_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = temp_groups_data.get(user_id)
    if not data and callback.data not in ['save_groups', 'select_all_groups']:
        await callback.message.edit_text("Сессия истекла. Начните заново.")
        await callback.answer()
        return

    if callback.data == 'save_groups':
        if user_id in temp_groups_data:
            del temp_groups_data[user_id]
        await callback.message.delete()
        await callback.message.answer("✅ Выбранные группы сохранены.", reply_markup=get_groups_kb())
        await callback.answer()
        await state.set_state(GroupStates.main)
        return

    if callback.data == 'select_all_groups':
        all_groups = data.get('groups', [])
        settings = user_mailing_settings.get(user_id, {})
        existing = settings.get('groups_list', [])
        existing_ids = {g['id'] for g in existing}
        added_count = 0
        for g in all_groups:
            if g['id'] not in existing_ids:
                existing.append(g)
                added_count += 1
        if added_count:
            settings['groups_list'] = existing
            settings['groups_count'] = len(existing)
            user_mailing_settings[user_id] = settings
            save_mailing_data()
            await callback.answer(f"✅ Добавлено {added_count} групп (пропущены дубликаты).", show_alert=True)
        else:
            await callback.answer("Все группы уже добавлены.", show_alert=True)
        page = data.get('page', 0)
        kb = build_groups_inline(all_groups, page)
        await callback.message.edit_reply_markup(reply_markup=kb)
        return

    if callback.data.startswith('groups_page_'):
        page = int(callback.data.split('_')[-1])
        groups = data.get('groups', [])
        kb = build_groups_inline(groups, page)
        data['page'] = page
        temp_groups_data[user_id] = data
        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer()
        return

    group_id = int(callback.data.split('_')[-1])
    groups = data.get('groups', [])
    selected_group = next((g for g in groups if g['id'] == group_id), None)
    if not selected_group:
        await callback.answer("Группа не найдена.", show_alert=True)
        return
    settings = user_mailing_settings.get(user_id, {})
    existing = settings.get('groups_list', [])
    if any(g['id'] == group_id for g in existing):
        await callback.answer("Эта группа уже добавлена.", show_alert=True)
        return
    existing.append(selected_group)
    settings['groups_list'] = existing
    settings['groups_count'] = len(existing)
    user_mailing_settings[user_id] = settings
    save_mailing_data()
    await callback.answer(f"✅ Группа '{selected_group['title']}' добавлена!", show_alert=True)
    page = data.get('page', 0)
    kb = build_groups_inline(groups, page)
    await callback.message.edit_reply_markup(reply_markup=kb)

# ====== ИНТЕРВАЛ ======
@router.message(F.text == "⏱ Интервал")
async def cycle_interval_menu(message: Message, state: FSMContext):
    await state.set_state(MailingStates.cycle_interval_setting)
    user_id = message.from_user.id
    settings = user_mailing_settings.get(user_id, {})
    current = settings.get("cycle_interval", 5)
    await message.answer(
        f"🔄 <b>Интервал между циклами</b>\n"
        f"⏱ Текущий интервал: {current} мин.\n\n"
        "Выберите время 👇",
        reply_markup=get_cycle_interval_kb()
    )

@router.callback_query(MailingStates.cycle_interval_setting, lambda c: c.data.startswith("cycle_"))
async def set_cycle_interval_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    value = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    settings = user_mailing_settings.get(user_id, {})
    settings["cycle_interval"] = value
    user_mailing_settings[user_id] = settings
    save_mailing_data()
    await state.set_state(MailingStates.panel)
    panel_text = get_panel_text(user_id)
    is_active = settings.get("is_active", False)
    await callback.message.edit_text(f"✅ Интервал между циклами установлен: {value} мин.", reply_markup=get_mailing_panel_kb(is_active))
    await callback.message.answer(panel_text, reply_markup=get_mailing_panel_kb(is_active))

@router.callback_query(MailingStates.cycle_interval_setting, lambda c: c.data == "go_to_message_interval")
async def go_to_message_interval_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(MailingStates.message_interval_setting)
    user_id = callback.from_user.id
    settings = user_mailing_settings.get(user_id, {})
    current = settings.get("interval", 5)
    await callback.message.edit_text(
        f"⏱ <b>Пауза между сообщениями</b>\n"
        f"⏱ Текущая пауза: {current} сек.\n\n"
        "Выберите время 👇",
        reply_markup=get_message_interval_kb()
    )

@router.callback_query(MailingStates.message_interval_setting, lambda c: c.data.startswith("msg_"))
async def set_message_interval_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    value = float(callback.data.split("_")[1])
    user_id = callback.from_user.id
    settings = user_mailing_settings.get(user_id, {})
    settings["interval"] = value
    user_mailing_settings[user_id] = settings
    save_mailing_data()
    await state.set_state(MailingStates.cycle_interval_setting)
    current_cycle = settings.get("cycle_interval", 5)
    await callback.message.edit_text(f"✅ Пауза между сообщениями установлена: {value} сек.")
    await callback.message.answer(
        f"🔄 <b>Интервал между циклами</b>\n"
        f"⏱ Текущий интервал: {current_cycle} мин.\n\n"
        "Выберите время 👇",
        reply_markup=get_cycle_interval_kb()
    )

@router.callback_query(MailingStates.message_interval_setting, lambda c: c.data == "pause_info")
async def pause_info_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📖 <b>Что такое пауза между сообщениями?</b>\n\n"
        "Это задержка между отправкой каждого следующего сообщения в рамках одного цикла рассылки.\n"
        "Например, если у вас выбрано 10 групп и пауза 5 секунд, то сообщения в эти группы будут отправляться с интервалом 5 секунд.\n\n"
        "Рекомендуется устанавливать паузу не менее 2-3 секунд, чтобы избежать блокировки со стороны Telegram.\n"
        "Для больших объёмов рассылки (более 100 групп) рекомендуется увеличить паузу до 5-10 секунд.",
        reply_markup=get_message_interval_kb()
    )

@router.callback_query(MailingStates.message_interval_setting, lambda c: c.data == "back_to_cycle_interval")
async def back_to_cycle_interval_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(MailingStates.cycle_interval_setting)
    user_id = callback.from_user.id
    settings = user_mailing_settings.get(user_id, {})
    current = settings.get("cycle_interval", 5)
    await callback.message.edit_text(
        f"🔄 <b>Интервал между циклами</b>\n"
        f"⏱ Текущий интервал: {current} мин.\n\n"
        "Выберите время 👇",
        reply_markup=get_cycle_interval_kb()
    )

# ====== СТАТИСТИКА (главное меню) ======
@router.message(F.text == "📊 Статистика")
async def stats_from_main(message: Message, state: FSMContext):
    user_id = message.from_user.id
    stats_text = get_stats_text(user_id)
    if stats_text is None:
        await message.answer(
            "📊 Статистика доступна только после запуска рассылки.\n"
            "Перейдите в раздел «Авто рассылка» для настройки и запуска.",
            reply_markup=main_menu_kb
        )
    else:
        await message.answer(stats_text, reply_markup=get_stats_main_kb())

# ====== ГЛОБАЛЬНЫЙ "НАЗАД" ======
@router.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main_global(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("⬅️ Возврат в главное меню.")
    await callback.message.answer("Выберите раздел 👇", reply_markup=main_menu_kb)