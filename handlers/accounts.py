import os
import json
import asyncio
import logging
from datetime import datetime
from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    AuthRestartError,
    FloodWaitError,
    PhoneNumberInvalidError,
    PhoneNumberUnoccupiedError,
    PhoneNumberBannedError,
    PasswordHashInvalidError,
)

from config import API_ID, API_HASH, MAX_ACCOUNTS, DATA_FILE
from states import AccountStates
from keyboards import (
    main_menu_kb,
    get_accounts_kb,
    get_login_method_kb,
    get_phone_reply_kb,
    get_code_kb,
    get_confirm_delete_kb,
    get_cancel_2fa_kb
)

logger = logging.getLogger(__name__)
router = Router()

user_sessions = {}
user_accounts = {}
temp_data = {}

def save_accounts_data():
    data = {"user_accounts": user_accounts}
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"✅ Аккаунты сохранены в {DATA_FILE}")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения аккаунтов: {e}")

def load_accounts_data():
    global user_accounts, user_sessions
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                user_accounts = data.get("user_accounts", {})
            logger.info(f"📂 Аккаунты загружены из {DATA_FILE}")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки аккаунтов: {e}")
            user_accounts = {}
    else:
        user_accounts = {}

    user_sessions = {}
    for user_id, accounts in list(user_accounts.items()):
        user_sessions[user_id] = []
        for acc in accounts[:]:
            session_path = acc.get("session_path")
            if session_path and os.path.exists(session_path):
                try:
                    client = TelegramClient(session_path, API_ID, API_HASH)
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        authorized = loop.run_until_complete(check_client(client))
                    finally:
                        loop.close()
                    if authorized:
                        user_sessions[user_id].append(client)
                        acc["client"] = client
                        logger.info(f"✅ Сессия восстановлена для {acc.get('phone')}")
                    else:
                        logger.warning(f"⚠️ Клиент не авторизован: {acc.get('phone')}, удаляем")
                        accounts.remove(acc)
                        save_accounts_data()
                except Exception as e:
                    logger.error(f"❌ Ошибка восстановления клиента для {acc.get('phone')}: {e}")
                    if acc in accounts:
                        accounts.remove(acc)
                        save_accounts_data()
            else:
                logger.warning(f"⚠️ Файл сессии не найден: {session_path}, удаляем аккаунт {acc.get('phone')}")
                if acc in accounts:
                    accounts.remove(acc)
                    save_accounts_data()

async def check_client(client):
    try:
        await client.connect()
        if await client.is_user_authorized():
            return True
        else:
            await client.disconnect()
            return False
    except Exception as e:
        logger.error(f"Ошибка проверки клиента: {e}")
        return False

def get_unique_session_path(user_id: int, phone: str) -> str:
    os.makedirs("sessions", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"sessions/user_{user_id}_{phone}_{timestamp}.session"

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
        "Это действие необратимо.",
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

        save_accounts_data()
        await callback.message.edit_text("✅ Профиль успешно удалён.", reply_markup=get_accounts_kb())
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

@router.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main_from_profiles(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("⬅️ Возврат в главное меню.")
    await callback.message.answer("Выберите раздел 👇", reply_markup=main_menu_kb)