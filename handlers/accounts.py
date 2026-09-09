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
from telethon.tl.types import KeyboardButtonUrl, KeyboardButtonCallback, ReplyInlineMarkup, KeyboardButtonRow

from config import DATA_FILE, BOT_USERNAME, BOT_TOKEN
from states import TextMessageStates, MailingStates, GroupStates
from keyboards import (
    main_menu_kb, get_menu_text_kb, get_count_kb, get_buttons_count_kb,
    get_home_kb, get_example_kb, get_cancel_kb, get_mailing_panel_kb,
    get_autostop_kb, get_mention_kb, get_stats_kb, get_stats_main_kb,
    get_groups_kb, build_groups_inline, build_groups_list_inline,
    get_cycle_interval_kb, get_message_interval_kb, get_schedule_kb
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
    return ""

# ======= ФУНКЦИИ ДЛЯ РАБОТЫ С СООБЩЕНИЯМИ =======
def extract_message_data(message: Message) -> dict:
    data = {}
    if message.text:
        data["text"] = message.text
        data["html_text"] = message.html_text or message.text
    else:
        data["text"] = ""
        data["html_text"] = ""

    if message.caption:
        data["caption"] = message.caption
        data["html_caption"] = message.caption
        if not data["text"]:
            data["text"] = message.caption
            data["html_text"] = message.caption

    data["entities"] = message.entities if message.entities else []
    data["caption_entities"] = message.caption_entities if message.caption_entities else []
    data["buttons"] = []
    data["is_forward"] = False
    data["chat_id"] = message.chat.id
    data["message_id"] = message.message_id

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

    return data

async def send_message_to_group(client, group_entity, message_data: dict):
    try:
        if message_data.get("is_forward") is True:
            chat_id = message_data.get("chat_id")
            message_id = message_data.get("message_id")
            if not chat_id or not message_id:
                logger.error("❌ Нет данных для пересылки")
                return False, "Нет данных для пересылки"
            try:
                msg = await client.get_messages(chat_id, ids=message_id)
                if not msg:
                    logger.error(f"❌ Сообщение {message_id} не найдено в чате {chat_id}")
                    return False, "Сообщение не найдено"
                await client.forward_messages(
                    entity=group_entity,
                    messages=msg,
                    from_peer=chat_id
                )
                logger.info(f"✅ Переслано в группу {group_entity.id}")
                return True, None
            except Exception as e:
                logger.error(f"❌ Ошибка пересылки: {e}")
                return False, str(e)

        text = message_data.get("html_text") or message_data.get("text") or ""
        caption = message_data.get("caption") or message_data.get("text") or ""
        if message_data.get("media"):
            final_text = caption
        else:
            final_text = text

        media = message_data.get("media")
        media_type = message_data.get("media_type")
        buttons = message_data.get("buttons")

        reply_markup = None
        if buttons:
            keyboard_buttons = []
            for btn_text, btn_value in buttons:
                if btn_value.startswith(("http://", "https://")):
                    keyboard_buttons.append(KeyboardButtonUrl(text=btn_text, url=btn_value))
                else:
                    keyboard_buttons.append(KeyboardButtonCallback(text=btn_text, data=btn_value.encode()))
            rows = [KeyboardButtonRow(buttons=keyboard_buttons[i:i+1]) for i in range(0, len(keyboard_buttons), 1)]
            reply_markup = ReplyInlineMarkup(rows=rows)

        if media:
            if media_type == "photo":
                await client.send_file(
                    group_entity,
                    file=media,
                    caption=final_text,
                    parse_mode="html",
                    buttons=reply_markup   # исправлено
                )
            elif media_type == "video":
                await client.send_file(
                    group_entity,
                    file=media,
                    caption=final_text,
                    parse_mode="html",
                    buttons=reply_markup
                )
            elif media_type == "document":
                await client.send_file(
                    group_entity,
                    file=media,
                    caption=final_text,
                    parse_mode="html",
                    buttons=reply_markup
                )
            elif media_type == "audio":
                await client.send_file(
                    group_entity,
                    file=media,
                    caption=final_text,
                    parse_mode="html",
                    buttons=reply_markup
                )
            elif media_type == "voice":
                await client.send_file(
                    group_entity,
                    file=media,
                    caption=final_text,
                    parse_mode="html",
                    buttons=reply_markup
                )
            elif media_type == "animation":
                await client.send_file(
                    group_entity,
                    file=media,
                    caption=final_text,
                    parse_mode="html",
                    buttons=reply_markup
                )
            elif media_type == "sticker":
                await client.send_file(
                    group_entity,
                    file=media,
                    buttons=reply_markup
                )
            else:
                await client.send_file(
                    group_entity,
                    file=media,
                    caption=final_text,
                    parse_mode="html",
                    buttons=reply_markup
                )
            logger.info(f"✅ Отправлено медиа в группу {group_entity.id}")
        else:
            if final_text:
                await client.send_message(
                    group_entity,
                    message=final_text,
                    parse_mode="html",
                    buttons=reply_markup   # исправлено
                )
            else:
                logger.warning("⚠️ Нет текста и медиа для отправки")
                return False, "Нет контента"
            logger.info(f"✅ Отправлен текст в группу {group_entity.id}")

        return True, None

    except FloodWaitError as e:
        wait_seconds = e.seconds
        logger.warning(f"⏳ FloodWait: ждём {wait_seconds} сек.")
        await asyncio.sleep(wait_seconds)
        return await send_message_to_group(client, group_entity, message_data)
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
        return False, str(e)

async def mailing_task(user_id: int):
    settings = user_mailing_settings.get(user_id, {})
    stats = user_mailing_stats.get(user_id, {})
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

                success, error = await send_message_to_group(client, group_entity, current_msg)
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


# =================== ОСТАЛЬНЫЕ ОБРАБОТЧИКИ ===================
@router.message(F.text == "👤 Профили")
async def accounts_menu(message: Message, state: FSMContext):
    await state.set_state(AccountStates.main)
    user_id = message.from_user.id
    accounts = user_accounts.get(user_id, [])
    count = len(accounts)
    text = f"👤 <b>Профили</b> ({count}/{MAX_ACCOUNTS})\n\n"
    if count == 0:
        text += "📭 Профиль еще не добавлен.\n\n"
    else:
        for acc in accounts:
            text += f"• {acc.get('first_name', '')} {acc.get('last_name', '')} (@{acc.get('username', 'нет')})\n"
    text += f"\nℹ️ На обычном тарифе доступен только 1 профиль"
    await message.answer(text, reply_markup=get_accounts_kb())

@router.callback_query(AccountStates.main, lambda c: c.data == "add_profile")
async def add_account_start_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    if len(user_accounts.get(user_id, [])) >= MAX_ACCOUNTS:
        await callback.message.edit_text(
            f"❌ Вы достигли максимального количества профилей ({MAX_ACCOUNTS}).\n"
            "🗑 Удалите существующий профиль или перейдите на PRO‑тариф.",
            reply_markup=get_accounts_kb()
        )
        return
    await state.set_state(AccountStates.adding_phone)
    await callback.message.edit_text(
        "➕ <b>Добавьте профиль</b>\n\n"
        "🔒 Аккаунт используется только для авторассылки. Личные переписки НЕ читаются и НЕ сохраняются.\n"
        "Выберите способ входа 👇",
        reply_markup=get_login_method_kb()
    )

@router.callback_query(AccountStates.adding_phone, lambda c: c.data == "sms_login")
async def sms_login_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AccountStates.adding_phone)
    user_id = callback.from_user.id
    if user_id in temp_data:
        try:
            await temp_data[user_id]["client"].disconnect()
        except:
            pass
        del temp_data[user_id]
    await callback.message.edit_text(
        "📞 Введите номер телефона вручную (в формате +7XXXXXXXXXX)\n"
        "Или нажмите кнопку ниже, чтобы отправить контакт."
    )
    await callback.message.answer(
        "📱 Введите номер или используйте кнопку:",
        reply_markup=get_phone_reply_kb()
    )

@router.message(AccountStates.adding_phone, F.text == "⬅️ Назад")
async def back_from_phone_reply(message: Message, state: FSMContext):
    await state.set_state(AccountStates.main)
    user_id = message.from_user.id
    accounts = user_accounts.get(user_id, [])
    count = len(accounts)
    text = f"👤 <b>Профили</b> ({count}/{MAX_ACCOUNTS})\n\n"
    if count == 0:
        text += "📭 Профиль еще не добавлен.\n\n"
    else:
        for acc in accounts:
            text += f"• {acc.get('first_name', '')} {acc.get('last_name', '')} (@{acc.get('username', 'нет')})\n"
    text += f"\nℹ️ На обычном тарифе доступен только 1 профиль"
    await message.answer(text, reply_markup=get_accounts_kb())

@router.message(AccountStates.adding_phone, F.contact)
async def got_contact(message: Message, state: FSMContext):
    contact = message.contact
    phone = contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    await process_phone(phone, message, state)

@router.message(AccountStates.adding_phone, F.text)
async def got_phone_text(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        return
    phone = message.text.strip()
    if not phone.startswith("+"):
        await message.answer("⚠️ Номер должен начинаться с '+'. Попробуйте снова.")
        return
    if not phone[1:].isdigit():
        await message.answer("⚠️ Номер должен содержать только цифры после '+'. Попробуйте снова.")
        return
    await process_phone(phone, message, state)

async def process_phone(phone: str, message: Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"Попытка входа с номером {phone} для пользователя {user_id}")

    if user_id in temp_data:
        try:
            await temp_data[user_id]["client"].disconnect()
        except:
            pass
        del temp_data[user_id]

    session_path = get_unique_session_path(user_id, phone)
    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()

    try:
        result = await client.send_code_request(phone)
        temp_data[user_id] = {
            "phone": phone,
            "phone_code_hash": result.phone_code_hash,
            "client": client,
            "session_path": session_path
        }
        await state.set_state(AccountStates.waiting_code)
        logger.info(f"Код отправлен на номер {phone}")
        await message.answer(
            f"✅ Код подтверждения отправлен!\n\n"
            f"📱 Ваш номер: {phone}\n"
            "---------------------------------------\n"
            "Введите код из SMS. Можно с точкой (например, 43.650) или без.\n"
            "Если код не приходит в течение минуты, нажмите «🔄 Повторить».",
            reply_markup=get_code_kb()
        )
        await message.answer("🔢 Введите код:", reply_markup=ReplyKeyboardRemove())
    except PhoneNumberInvalidError:
        await client.disconnect()
        await message.answer("❌ Неверный номер телефона. Проверьте формат.", reply_markup=get_phone_reply_kb())
        await state.set_state(AccountStates.adding_phone)
    except PhoneNumberUnoccupiedError:
        await client.disconnect()
        await message.answer("❌ Этот номер не зарегистрирован в Telegram.", reply_markup=get_phone_reply_kb())
        await state.set_state(AccountStates.adding_phone)
    except PhoneNumberBannedError:
        await client.disconnect()
        await message.answer("❌ Этот номер заблокирован в Telegram.", reply_markup=get_phone_reply_kb())
        await state.set_state(AccountStates.adding_phone)
    except FloodWaitError as e:
        await client.disconnect()
        await message.answer(f"⏳ Слишком много попыток. Подождите {e.seconds} сек.", reply_markup=get_phone_reply_kb())
        await state.set_state(AccountStates.adding_phone)
    except AuthRestartError:
        await client.disconnect()
        await message.answer("⚠️ Ошибка авторизации. Попробуйте ещё раз.", reply_markup=get_phone_reply_kb())
        await state.set_state(AccountStates.adding_phone)
    except Exception as e:
        await client.disconnect()
        logger.error(f"Ошибка при отправке кода: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}", reply_markup=get_phone_reply_kb())
        await state.set_state(AccountStates.adding_phone)

@router.message(AccountStates.waiting_code)
async def enter_code(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = temp_data.get(user_id)
    if not data:
        await message.answer("⏳ Сессия истекла. Начните заново.", reply_markup=get_accounts_kb())
        await state.set_state(AccountStates.main)
        return

    code = message.text.strip()
    code = code.replace(" ", "").replace(".", "")
    if not code.isdigit():
        await message.answer("⚠️ Код должен содержать только цифры. Попробуйте снова.")
        return

    client = data["client"]
    phone = data["phone"]
    phone_code_hash = data["phone_code_hash"]

    try:
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        me = await client.get_me()
        await save_account_profile(user_id, me, phone, client, data["session_path"], message, state)
    except SessionPasswordNeededError:
        await state.set_state(AccountStates.waiting_2fa_password)
        temp_data[user_id]["client"] = client
        await message.answer(
            "🔐 Для этого аккаунта включена двухфакторная аутентификация.\n"
            "Введите пароль от аккаунта:",
            reply_markup=get_cancel_2fa_kb()
        )
    except PhoneCodeInvalidError:
        await message.answer("❌ Неверный код. Попробуйте снова.", reply_markup=get_code_kb())
    except PhoneCodeExpiredError:
        await message.answer("❌ Код истёк. Запросите новый через «🔄 Повторить».", reply_markup=get_code_kb())
    except Exception as e:
        logger.error(f"Ошибка входа: {e}")
        await message.answer(f"❌ Ошибка входа: {str(e)}", reply_markup=get_code_kb())

@router.message(AccountStates.waiting_2fa_password)
async def enter_2fa_password(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = temp_data.get(user_id)
    if not data:
        await message.answer("⏳ Сессия истекла. Начните заново.", reply_markup=get_accounts_kb())
        await state.set_state(AccountStates.main)
        return

    password = message.text.strip()
    if not password:
        await message.answer("Пароль не может быть пустым. Введите пароль.")
        return

    client = data["client"]

    try:
        await client.sign_in(password=password)
        me = await client.get_me()
        await save_account_profile(
            user_id, me, data["phone"], client,
            data["session_path"], message, state
        )
    except PasswordHashInvalidError:
        await message.answer("❌ Неверный пароль. Попробуйте снова.", reply_markup=get_cancel_2fa_kb())
    except Exception as e:
        logger.error(f"Ошибка входа с паролем: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}", reply_markup=get_cancel_2fa_kb())

async def save_account_profile(user_id: int, me, phone: str, client, session_path: str, message: Message, state: FSMContext):
    acc_info = {
        "phone": phone,
        "first_name": me.first_name,
        "last_name": me.last_name or "",
        "username": me.username or "нет",
        "user_id": me.id,
        "session_path": session_path
    }
    if user_id not in user_accounts:
        user_accounts[user_id] = []
    user_accounts[user_id].append(acc_info)
    user_sessions[user_id] = user_sessions.get(user_id, [])
    user_sessions[user_id].append(client)
    if user_id in temp_data:
        del temp_data[user_id]
    save_accounts_data()
    await state.set_state(AccountStates.main)
    await message.answer(
        f"✅ Профиль добавлен: {me.first_name} {me.last_name or ''} (@{me.username or 'нет'})",
        reply_markup=get_accounts_kb()
    )

@router.callback_query(AccountStates.adding_phone, lambda c: c.data == "back_to_accounts")
async def back_to_accounts_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AccountStates.main)
    user_id = callback.from_user.id
    accounts = user_accounts.get(user_id, [])
    count = len(accounts)
    text = f"👤 <b>Профили</b> ({count}/{MAX_ACCOUNTS})\n\n"
    if count == 0:
        text += "📭 Профиль еще не добавлен.\n\n"
    else:
        for acc in accounts:
            text += f"• {acc.get('first_name', '')} {acc.get('last_name', '')} (@{acc.get('username', 'нет')})\n"
    text += f"\nℹ️ На обычном тарифе доступен только 1 профиль"
    await callback.message.edit_text(text, reply_markup=get_accounts_kb())

@router.callback_query(AccountStates.waiting_code, lambda c: c.data == "code_hint")
async def code_hint_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📌 <b>Инструкция</b>\n"
        "Введите код из SMS. Если код, например, 43650, введите его как 43.650 (с точкой) или без точки.\n"
        "Бот автоматически удалит все точки и пробелы.\n\n"
        "❓ Если код не приходит в SMS, проверьте:\n"
        "1️⃣ Правильно ли введён номер (с + и кодом страны).\n"
        "2️⃣ Есть ли у вас доступ к этому номеру в Telegram.\n"
        "3️⃣ Не блокирует ли ваш оператор SMS от Telegram.\n"
        "4️⃣ Попробуйте запросить код повторно через «🔄 Повторить».",
        reply_markup=get_code_kb()
    )

@router.callback_query(AccountStates.waiting_code, lambda c: c.data == "retry_phone")
async def retry_phone_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    if user_id in temp_data:
        try:
            await temp_data[user_id]["client"].disconnect()
        except:
            pass
        del temp_data[user_id]
    await state.set_state(AccountStates.adding_phone)
    await callback.message.edit_text(
        "📞 Введите номер телефона заново.\nПример: +19876001213",
        reply_markup=get_phone_reply_kb()
    )

@router.callback_query(AccountStates.waiting_2fa_password, lambda c: c.data == "back_to_accounts")
async def back_from_2fa_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    if user_id in temp_data:
        try:
            await temp_data[user_id]["client"].disconnect()
        except:
            pass
        del temp_data[user_id]
    await state.set_state(AccountStates.main)
    accounts = user_accounts.get(user_id, [])
    count = len(accounts)
    text = f"👤 <b>Профили</b> ({count}/{MAX_ACCOUNTS})\n\n"
    if count == 0:
        text += "📭 Профиль еще не добавлен.\n\n"
    else:
        for acc in accounts:
            text += f"• {acc.get('first_name', '')} {acc.get('last_name', '')} (@{acc.get('username', 'нет')})\n"
    text += f"\nℹ️ На обычном тарифе доступен только 1 профиль"
    await callback.message.edit_text(text, reply_markup=get_accounts_kb())

# =================== УДАЛЕНИЕ ПРОФИЛЯ (с очисткой всех данных) ===================
@router.callback_query(AccountStates.main, lambda c: c.data == "delete_profile")
async def delete_profile_start_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    accounts = user_accounts.get(user_id, [])
    if not accounts:
        await callback.message.edit_text("❌ У вас нет добавленных профилей.", reply_markup=get_accounts_kb())
        return
    acc = accounts[0]
    await state.update_data(profile_to_delete=acc)
    await state.set_state(AccountStates.deleting_confirm)
    await callback.message.edit_text(
        f"⚠️ Вы уверены, что хотите удалить профиль:\n"
        f"{acc.get('first_name', '')} {acc.get('last_name', '')} (@{acc.get('username', 'нет')})\n\n"
        "Это действие необратимо.\n"
        "Будут удалены все настройки, статистика и данные рассылки.",
        reply_markup=get_confirm_delete_kb()
    )

@router.callback_query(AccountStates.deleting_confirm, lambda c: c.data == "confirm_delete_yes")
async def confirm_delete_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    data = await state.get_data()
    acc = data.get("profile_to_delete")
    if not acc:
        await callback.message.edit_text("Ошибка: профиль не найден.", reply_markup=get_accounts_kb())
        await state.set_state(AccountStates.main)
        return

    accounts = user_accounts.get(user_id, [])
    if acc in accounts:
        accounts.remove(acc)
        user_accounts[user_id] = accounts

        # Удаляем файл сессии
        session_path = acc.get("session_path")
        if session_path and os.path.exists(session_path):
            try:
                os.remove(session_path)
                logger.info(f"Файл сессии удалён: {session_path}")
            except Exception as e:
                logger.error(f"Ошибка удаления файла сессии {session_path}: {e}")

        # Отключаем клиент
        client = acc.get("client")
        if not client:
            for c in user_sessions.get(user_id, []):
                if hasattr(c, 'session_path') and c.session_path == acc.get("session_path"):
                    client = c
                    break
        if client:
            try:
                await client.disconnect()
            except:
                pass
            if user_id in user_sessions:
                user_sessions[user_id] = [c for c in user_sessions[user_id] if c != client]

        # ===== ОЧИСТКА ВСЕХ ДАННЫХ ПОЛЬЗОВАТЕЛЯ (АСИНХРОННАЯ) =====
        await clear_user_data(user_id)

        # Сохраняем изменения
        save_accounts_data()

        await callback.message.edit_text("✅ Профиль и все связанные данные успешно удалены.", reply_markup=get_accounts_kb())
    else:
        await callback.message.edit_text("❌ Профиль уже был удалён.", reply_markup=get_accounts_kb())
    await state.set_state(AccountStates.main)

@router.callback_query(AccountStates.deleting_confirm, lambda c: c.data == "confirm_delete_no")
async def cancel_delete_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AccountStates.main)
    user_id = callback.from_user.id
    accounts = user_accounts.get(user_id, [])
    count = len(accounts)
    text = f"👤 <b>Профили</b> ({count}/{MAX_ACCOUNTS})\n\n"
    if count == 0:
        text += "📭 Профиль еще не добавлен.\n\n"
    else:
        for acc in accounts:
            text += f"• {acc.get('first_name', '')} {acc.get('last_name', '')} (@{acc.get('username', 'нет')})\n"
    text += f"\nℹ️ На обычном тарифе доступен только 1 профиль"
    await callback.message.edit_text(text, reply_markup=get_accounts_kb())

# =================== QR-ВХОД ===================
@router.callback_query(AccountStates.adding_phone, lambda c: c.data == "qr_login")
async def qr_login_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id

    loading_msg = await callback.message.answer("⏳ Генерируем QR-код, пожалуйста, подождите...")

    if user_id in temp_data:
        try:
            await temp_data[user_id]["client"].disconnect()
        except:
            pass
        del temp_data[user_id]

    session_path = get_unique_session_path(user_id, f"qr_{user_id}")
    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()

    try:
        qr_login = await client.qr_login()

        temp_data[user_id] = {
            "client": client,
            "session_path": session_path,
            "qr_login": qr_login,
        }
        await state.set_state(AccountStates.qr_code)

        qr = qrcode.QRCode(border=1, box_size=10)
        qr.add_data(qr_login.url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        bio = BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)

        await loading_msg.delete()

        await callback.message.answer_photo(
            photo=BufferedInputFile(bio.getvalue(), filename="qr.png"),
            caption=(
                "📷 **Вход по QR-коду**\n\n"
                "1️⃣ Откройте Telegram на телефоне\n"
                "2️⃣ Настройки → Устройства → Привязать устройство\n"
                "3️⃣ Наведите камеру на этот QR-код\n\n"
                "⏳ QR-код действителен ~30 секунд\n"
                "🔄 Он обновится автоматически\n\n"
                "📌 После сканирования аккаунт добавится автоматически."
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить QR", callback_data="qr_refresh")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_accounts")]
            ])
        )

        if user_id in qr_tasks and not qr_tasks[user_id].done():
            qr_tasks[user_id].cancel()
        qr_tasks[user_id] = asyncio.create_task(check_qr_login(user_id, callback.message, state))

    except Exception as e:
        await loading_msg.delete()
        logger.error(f"Ошибка QR-логина: {e}")
        await callback.message.answer(f"❌ Ошибка: {str(e)}\nПопробуйте снова.")

@router.callback_query(AccountStates.qr_code, lambda c: c.data == "qr_refresh")
async def qr_refresh_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    data = temp_data.get(user_id)
    if not data:
        await callback.message.answer("❌ Сессия истекла. Начните заново.")
        await state.set_state(AccountStates.adding_phone)
        return

    qr_login = data.get("qr_login")
    if not qr_login:
        await callback.message.answer("❌ QR-логин не найден.")
        return

    try:
        await callback.message.answer("⏳ Перегенерируем QR-код...")

        qr_login.recreate()
        qr = qrcode.QRCode(border=1, box_size=10)
        qr.add_data(qr_login.url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        bio = BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)

        await callback.message.edit_media(
            types.InputMediaPhoto(media=BufferedInputFile(bio.getvalue(), filename="qr.png")),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить QR", callback_data="qr_refresh")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_accounts")]
            ])
        )
        await callback.answer("🔄 QR-код обновлён!")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка обновления QR: {str(e)}")

@router.callback_query(AccountStates.qr_code, lambda c: c.data == "back_to_accounts")
async def back_from_qr(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id

    if user_id in temp_data:
        try:
            await temp_data[user_id]["client"].disconnect()
        except:
            pass
        del temp_data[user_id]
    if user_id in qr_tasks:
        if not qr_tasks[user_id].done():
            qr_tasks[user_id].cancel()
        del qr_tasks[user_id]

    await state.set_state(AccountStates.adding_phone)
    await callback.message.delete()
    await callback.message.answer(
        "➕ <b>Добавьте профиль</b>\n\n"
        "🔒 Аккаунт используется только для авторассылки. Личные переписки НЕ читаются и НЕ сохраняются.\n"
        "Выберите способ входа 👇",
        reply_markup=get_login_method_kb()
    )

async def check_qr_login(user_id: int, message: types.Message, state: FSMContext):
    data = temp_data.get(user_id)
    if not data:
        return

    qr_login = data.get("qr_login")
    client = data.get("client")

    try:
        await qr_login.wait(timeout=60)
        me = await client.get_me()
        if user_id in qr_tasks and qr_tasks[user_id] != asyncio.current_task():
            qr_tasks[user_id].cancel()

        await save_account_profile(
            user_id,
            me,
            me.phone,
            client,
            data["session_path"],
            message,
            state
        )
        await message.answer("✅ Аккаунт успешно добавлен через QR-код!")
        if user_id in temp_data:
            del temp_data[user_id]
        if user_id in qr_tasks:
            del qr_tasks[user_id]

    except asyncio.CancelledError:
        pass
    except Exception as e:
        await message.answer(f"❌ Ошибка входа по QR: {str(e)}\nПопробуйте снова.")
        await client.disconnect()
        if user_id in temp_data:
            del temp_data[user_id]
        if user_id in qr_tasks:
            del qr_tasks[user_id]

# =================== ВОЗВРАТ В ГЛАВНОЕ МЕНЮ ===================
@router.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main_from_profiles(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("⬅️ Возврат в главное меню.")
    await callback.message.answer("Выберите раздел 👇", reply_markup=main_menu_kb)