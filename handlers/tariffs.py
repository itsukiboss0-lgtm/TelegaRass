import os
import json
import logging
from datetime import datetime, timedelta
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import DATA_FILE, ADMINS, BOT_USERNAME
from states import TariffStates
from keyboards import (
    get_tariff_main_kb,
    get_tariff_duration_kb,
    get_tariff_payment_kb,
    main_menu_kb
)

logger = logging.getLogger(__name__)
router = Router()

PRICE_STARS = {1: 10, 7: 55, 15: 100, 30: 175, 60: 300, 90: 450}
user_subscriptions = {}
user_referrals = {}

def load_referral_data():
    global user_referrals
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            user_referrals = data.get("user_referrals", {})
    else:
        user_referrals = {}

def save_referral_data():
    data = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    data["user_referrals"] = user_referrals
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

def get_referral_link(user_id: int) -> str:
    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

def add_referral(referrer_id: int, new_user_id: int) -> bool:
    if referrer_id == new_user_id:
        return False
    if referrer_id not in user_referrals:
        user_referrals[referrer_id] = []
    if new_user_id in user_referrals[referrer_id]:
        return False
    user_referrals[referrer_id].append(new_user_id)
    save_referral_data()
    activate_subscription(referrer_id, 0.5)
    return True

def get_referral_count(user_id: int) -> int:
    return len(user_referrals.get(user_id, []))

def get_subscription_text(user_id: int) -> str:
    sub = user_subscriptions.get(user_id, {})
    is_active = sub.get("active", False)
    expires_at = sub.get("expires_at")
    if is_active and expires_at:
        now = datetime.now()
        if expires_at > now:
            delta = expires_at - now
            hours = delta.total_seconds() / 3600
            if hours >= 24:
                days = hours // 24
                status = f"✅ Активна (осталось {int(days)} дн.)"
            else:
                status = f"✅ Активна (осталось {int(hours)} ч.)"
        else:
            status = "❌ Истекла"
    elif is_active:
        status = "✅ Активна"
    else:
        status = "❌ Неактивна"
    return status

def is_subscription_active(user_id: int) -> bool:
    sub = user_subscriptions.get(user_id, {})
    if not sub.get("active", False):
        return False
    expires_at = sub.get("expires_at")
    if expires_at and datetime.now() > expires_at:
        sub["active"] = False
        user_subscriptions[user_id] = sub
        return False
    return True

def activate_subscription(user_id: int, days: float):
    expires_at = datetime.now() + timedelta(days=days)
    sub = user_subscriptions.get(user_id, {})
    if sub.get("active", False) and sub.get("expires_at"):
        existing_expires = sub["expires_at"]
        if existing_expires > datetime.now():
            expires_at = existing_expires + timedelta(days=days)
    user_subscriptions[user_id] = {
        "active": True,
        "expires_at": expires_at,
        "days": sub.get("days", 0) + days
    }
    logger.info(f"Подписка активирована для {user_id} на {days} дней (всего {user_subscriptions[user_id]['days']})")
    save_referral_data()

def check_expired_subscriptions():
    now = datetime.now()
    for user_id, sub in user_subscriptions.items():
        if sub.get("active", False):
            expires_at = sub.get("expires_at")
            if expires_at and now > expires_at:
                sub["active"] = False
                user_subscriptions[user_id] = sub
                logger.info(f"Подписка для {user_id} истекла")

# ====== КОМАНДЫ АДМИНИСТРАТОРА ======
@router.message(Command("grant_pro"))
async def grant_pro_command(message: Message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ Формат: /grant_pro <user_id> <days>\nПример: /grant_pro 123456 30")
        return

    try:
        target_user_id = int(args[1])
        days = float(args[2])
        if days <= 0:
            await message.answer("❌ Количество дней должно быть больше 0.")
            return
        activate_subscription(target_user_id, days)
        await message.answer(f"✅ Подписка PRO активирована для пользователя {target_user_id} на {days} дней.")
    except ValueError:
        await message.answer("❌ Некорректные данные. Используйте /grant_pro <user_id> <days>")

@router.message(Command("mysub"))
async def my_subscription_command(message: Message):
    user_id = message.from_user.id
    text = get_subscription_text(user_id)
    await message.answer(f"📊 Ваша подписка:\n{text}")

# ====== ОСНОВНОЙ ОБРАБОТЧИК ТАРИФОВ ======
@router.message(F.text == "💎 Тарифы")
async def tariff_main(message: Message, state: FSMContext):
    await state.set_state(TariffStates.main)
    user_id = message.from_user.id
    invited = get_referral_count(user_id)
    ref_link = get_referral_link(user_id)
    text = (
        "💎 <b>Mail Pulse Pro</b>\n\n"
        f"Подписка Pro: {get_subscription_text(user_id)}\n\n"
        "🌟 <b>Возможности PRO:</b>\n"
        "• Авто-рассылка без подписи бота\n"
        "• Пересылка в оригинальном формате (Free — копия)\n"
        "• Безлимит на сообщения в сутки (Free — 10 000)\n"
        "• Безлимит групп для рассылки (Free — 300)\n"
        "• До 5 подключённых аккаунтов (Free — 1)\n\n"
        "💰 <b>Прайс:</b>\n"
        "⭐ 10 / 1 день\n"
        "⭐ 55 / 7 дней\n"
        "⭐ 100 / 15 дней\n"
        "⭐ 175 / 30 дней\n"
        "⭐ 300 / 60 дней\n"
        "⭐ 450 / 90 дней\n\n"
        "₿ <b>USDT:</b> 0.16 / 1 день, 0.99 / 7 дней, 1.75 / 15 дней, 2.15 / 30 дней\n\n"
        "🎁 <b>Получить Бесплатно:</b>\n"
        "За каждого друга — 12 часов PRO, автоматически и сразу!\n"
        "Ваши друзья должны подписаться на все каналы!\n\n"
        f"👥 Вы пригласили: {invited}\n"
        f"🔗 Ваша ссылка: {ref_link}"
    )
    await message.answer(text, reply_markup=get_tariff_main_kb())

@router.callback_query(TariffStates.main, lambda c: c.data == "tariff_pay_stars")
async def tariff_pay_stars_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TariffStates.choosing_duration)
    await callback.message.edit_text(
        "⏳ <b>Выберите срок</b>\n\n"
        "После оплаты PRO активируется автоматически.\n"
        "Минимум 1, максимум 90 дней.",
        reply_markup=get_tariff_duration_kb()
    )

@router.callback_query(TariffStates.main, lambda c: c.data == "tariff_pay_crypto")
async def tariff_pay_crypto_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer("🚧 Оплата через CryptoBot временно недоступна.", show_alert=True)

@router.callback_query(TariffStates.main, lambda c: c.data == "tariff_cancel_pro")
async def cancel_pro_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    sub = user_subscriptions.get(user_id, {})
    if sub.get("active", False):
        sub["active"] = False
        user_subscriptions[user_id] = sub
        await callback.message.edit_text(
            "❌ Подписка PRO отменена.\n"
            "Теперь вы снова на Free-тарифе.",
            reply_markup=get_tariff_main_kb()
        )
    else:
        await callback.message.edit_text(
            "⚠️ У вас нет активной подписки PRO.",
            reply_markup=get_tariff_main_kb()
        )

@router.callback_query(TariffStates.choosing_duration, lambda c: c.data.startswith("tariff_duration_"))
async def tariff_duration_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    days = int(callback.data.split("_")[2])
    await state.update_data(selected_days=days)
    await callback.message.edit_text(
        f"Вы выбрали: {days} дн.\n\n"
        "💰 Нажмите «Купить» для оплаты звёздами.",
        reply_markup=get_tariff_duration_kb(selected_days=days)
    )

@router.callback_query(TariffStates.choosing_duration, lambda c: c.data.startswith("tariff_buy_stars_"))
async def tariff_buy_stars_callback(callback: CallbackQuery, state: FSMContext, bot):
    await callback.answer()
    days = int(callback.data.split("_")[3])
    data = await state.get_data()
    selected = data.get("selected_days")
    if selected != days:
        await callback.answer("Ошибка: выберите срок заново.", show_alert=True)
        return
    price = PRICE_STARS.get(days, 0)
    if price == 0:
        await callback.answer("Ошибка: неверная цена.", show_alert=True)
        return
    user_id = callback.from_user.id
    payload = f"pro_subscription_{user_id}_{days}_{int(datetime.now().timestamp())}"
    try:
        await bot.send_invoice(
            chat_id=callback.message.chat.id,
            title=f"Mail Pulse Pro — {days} дн.",
            description=f"Подписка Mail Pulse Pro на {days} дней.",
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=f"{days} дней PRO", amount=price)],
        )
        await state.set_state(TariffStates.payment_stars)
        await callback.message.delete()
        await callback.message.answer(
            "💳 Нажмите кнопку <b>Оплатить</b> под счётом, чтобы завершить покупку.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tariff_duration")]
            ])
        )
    except Exception as e:
        logger.error(f"Ошибка отправки инвойса: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка при создании счёта: {str(e)}\nПопробуйте позже.",
            reply_markup=get_tariff_duration_kb(selected_days=days)
        )

@router.pre_checkout_query(lambda query: True)
async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery, bot):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    logger.info(f"Pre-checkout query OK для {pre_checkout_query.from_user.id}")

@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, state: FSMContext):
    payment = message.successful_payment
    user_id = message.from_user.id
    payload = payment.invoice_payload
    try:
        parts = payload.split("_")
        if len(parts) >= 4 and parts[0] == "pro" and parts[1] == "subscription":
            days = int(parts[2])
            activate_subscription(user_id, days)
            logger.info(f"Успешная оплата для {user_id} на {days} дней, сумма: {payment.total_amount} {payment.currency}")
            await message.answer(
                f"✅ <b>Оплата прошла успешно!</b>\n\n"
                f"Подписка Mail Pulse Pro активирована на <b>{days} дней</b>.\n"
                f"Списано: {payment.total_amount} ⭐\n\n"
                "Теперь вам доступны все возможности PRO-версии! 🚀",
                reply_markup=get_tariff_main_kb()
            )
            await state.set_state(TariffStates.main)
        else:
            logger.warning(f"Неизвестный payload: {payload}")
            await message.answer(
                "⚠️ Оплата получена, но не удалось определить срок подписки.\n"
                "Пожалуйста, свяжитесь с поддержкой.",
                reply_markup=main_menu_kb
            )
    except Exception as e:
        logger.error(f"Ошибка обработки successful_payment: {e}")
        await message.answer(
            "⚠️ Произошла ошибка при активации подписки.\n"
            "Пожалуйста, свяжитесь с поддержкой.",
            reply_markup=main_menu_kb
        )

@router.callback_query(TariffStates.choosing_duration, lambda c: c.data == "back_to_tariff_main")
async def back_to_tariff_main_from_duration(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TariffStates.main)
    user_id = callback.from_user.id
    text = (
        "💎 <b>Mail Pulse Pro</b>\n\n"
        f"Подписка Pro: {get_subscription_text(user_id)}\n\n"
        "🌟 <b>Возможности PRO:</b>\n"
        "• Авто-рассылка без подписи бота\n"
        "• Пересылка в оригинальном формате (Free — копия)\n"
        "• Безлимит на сообщения в сутки (Free — 10 000)\n"
        "• Безлимит групп для рассылки (Free — 300)\n"
        "• До 5 подключённых аккаунтов (Free — 1)\n\n"
        "💰 <b>Прайс:</b>\n"
        "⭐ 10 / 1 день\n"
        "⭐ 55 / 7 дней\n"
        "⭐ 100 / 15 дней\n"
        "⭐ 175 / 30 дней\n"
        "⭐ 300 / 60 дней\n"
        "⭐ 450 / 90 дней\n\n"
        "🎁 <b>Получить Бесплатно:</b>\n"
        "За каждого друга — 12 часов PRO, автоматически и сразу!\n"
        "Ваши друзья должны подписаться на все каналы!"
    )
    await callback.message.edit_text(text, reply_markup=get_tariff_main_kb())

@router.callback_query(TariffStates.payment_stars, lambda c: c.data == "back_to_tariff_duration")
async def back_to_tariff_duration_from_payment(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TariffStates.choosing_duration)
    data = await state.get_data()
    days = data.get("selected_days", 1)
    await callback.message.edit_text(
        f"Вы выбрали: {days} дн.\n\n"
        "💰 Нажмите «Купить» для оплаты звёздами.",
        reply_markup=get_tariff_duration_kb(selected_days=days)
    )

@router.callback_query(TariffStates.main, lambda c: c.data == "back_to_main")
async def back_to_main_from_tariff(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("⬅️ Возврат в главное меню.")
    await callback.message.answer("Выберите раздел 👇", reply_markup=main_menu_kb)