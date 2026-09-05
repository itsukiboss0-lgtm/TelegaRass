from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

main_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Авто рассылка"), KeyboardButton(text="📝 Текст сообщения")],
        [KeyboardButton(text="⏱ Интервал"), KeyboardButton(text="👥 Настройка групп")],
        [KeyboardButton(text="👤 Профили"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="💎 Тарифы"), KeyboardButton(text="📖 Инструкция")],
        [KeyboardButton(text="❓ Помощь")]
    ],
    resize_keyboard=True,
    is_persistent=True
)

def get_menu_text_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Обычное", callback_data="type_ordinary")],
        [InlineKeyboardButton(text="🔄 Разные", callback_data="type_multiple")],
        [InlineKeyboardButton(text="🔗 С кнопками", callback_data="type_buttons")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])

def get_count_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="2️⃣", callback_data="count_2"),
         InlineKeyboardButton(text="3️⃣", callback_data="count_3"),
         InlineKeyboardButton(text="4️⃣", callback_data="count_4")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_choosing_type")]
    ])

def get_buttons_count_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣", callback_data="btncount_1"),
         InlineKeyboardButton(text="2️⃣", callback_data="btncount_2")],
        [InlineKeyboardButton(text="3️⃣", callback_data="btncount_3"),
         InlineKeyboardButton(text="4️⃣", callback_data="btncount_4")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main_message")]
    ])

def get_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Домой", callback_data="go_home")]
    ])

def get_example_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 Пример текста", callback_data="show_example")],
        [InlineKeyboardButton(text="🏠 Домой", callback_data="go_home")]
    ])

def get_cancel_kb(back_callback: str = "back_to_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]
    ])

def get_mailing_panel_kb(is_active: bool) -> InlineKeyboardMarkup:
    if is_active:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏹ Остановить", callback_data="stop_mailing"),
             InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")],
            [InlineKeyboardButton(text="⏱ Авто-стоп", callback_data="autostop_menu"),
             InlineKeyboardButton(text="🔔 Упоминания", callback_data="mention_menu")],
            [InlineKeyboardButton(text="📅 Расписание", callback_data="schedule_mailing"),
             InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Запустить", callback_data="start_mailing"),
             InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")],
            [InlineKeyboardButton(text="⏱ Авто-стоп", callback_data="autostop_menu"),
             InlineKeyboardButton(text="🔔 Упоминания", callback_data="mention_menu")],
            [InlineKeyboardButton(text="📅 Расписание", callback_data="schedule_mailing"),
             InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
        ])

def get_autostop_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ час", callback_data="autostop_1"),
         InlineKeyboardButton(text="2️⃣ часа", callback_data="autostop_2"),
         InlineKeyboardButton(text="3️⃣ часа", callback_data="autostop_3")],
        [InlineKeyboardButton(text="6️⃣ часов", callback_data="autostop_6"),
         InlineKeyboardButton(text="1️⃣2️⃣ часов", callback_data="autostop_12"),
         InlineKeyboardButton(text="1️⃣8️⃣ часов", callback_data="autostop_18")],
        [InlineKeyboardButton(text="2️⃣4️⃣ часа", callback_data="autostop_24"),
         InlineKeyboardButton(text="4️⃣8️⃣ часов", callback_data="autostop_48")],
        [InlineKeyboardButton(text="♾ Бесконечно", callback_data="autostop_infinite")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_panel")]
    ])

def get_mention_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Включить", callback_data="mention_on"),
         InlineKeyboardButton(text="❌ Выключить", callback_data="mention_off")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_panel")]
    ])

def get_stats_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_stats")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_panel")]
    ])

def get_stats_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])

def get_groups_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список", callback_data="groups_list"),
         InlineKeyboardButton(text="➕ Добавить", callback_data="groups_add")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])

def get_cycle_interval_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 мин", callback_data="cycle_1"),
         InlineKeyboardButton(text="2 мин", callback_data="cycle_2"),
         InlineKeyboardButton(text="3 мин", callback_data="cycle_3")],
        [InlineKeyboardButton(text="5 мин", callback_data="cycle_5"),
         InlineKeyboardButton(text="7 мин", callback_data="cycle_7"),
         InlineKeyboardButton(text="10 мин", callback_data="cycle_10")],
        [InlineKeyboardButton(text="15 мин", callback_data="cycle_15"),
         InlineKeyboardButton(text="20 мин", callback_data="cycle_20"),
         InlineKeyboardButton(text="30 мин", callback_data="cycle_30")],
        [InlineKeyboardButton(text="45 мин", callback_data="cycle_45"),
         InlineKeyboardButton(text="1 час", callback_data="cycle_60"),
         InlineKeyboardButton(text="1.5 часа", callback_data="cycle_90")],
        [InlineKeyboardButton(text="2 часа", callback_data="cycle_120"),
         InlineKeyboardButton(text="3 часа", callback_data="cycle_180"),
         InlineKeyboardButton(text="4 часа", callback_data="cycle_240")],
        [InlineKeyboardButton(text="⏱ Пауза между сообщениями", callback_data="go_to_message_interval")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_panel")]
    ])

def get_message_interval_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0.1 сек", callback_data="msg_0.1"),
         InlineKeyboardButton(text="0.5 сек", callback_data="msg_0.5"),
         InlineKeyboardButton(text="1 сек", callback_data="msg_1")],
        [InlineKeyboardButton(text="2 сек", callback_data="msg_2"),
         InlineKeyboardButton(text="3 сек", callback_data="msg_3"),
         InlineKeyboardButton(text="5 сек", callback_data="msg_5")],
        [InlineKeyboardButton(text="7 сек", callback_data="msg_7"),
         InlineKeyboardButton(text="10 сек", callback_data="msg_10"),
         InlineKeyboardButton(text="15 сек", callback_data="msg_15")],
        [InlineKeyboardButton(text="20 сек", callback_data="msg_20"),
         InlineKeyboardButton(text="25 сек", callback_data="msg_25"),
         InlineKeyboardButton(text="30 сек", callback_data="msg_30")],
        [InlineKeyboardButton(text="40 сек", callback_data="msg_40"),
         InlineKeyboardButton(text="50 сек", callback_data="msg_50"),
         InlineKeyboardButton(text="1 мин", callback_data="msg_60")],
        [InlineKeyboardButton(text="❓ Что такое пауза?", callback_data="pause_info")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_cycle_interval")]
    ])

def get_tariff_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оплатить Stars", callback_data="tariff_pay_stars")],
        [InlineKeyboardButton(text="₿ Оплатить Crypto", callback_data="tariff_pay_crypto")],
        [InlineKeyboardButton(text="❌ Отменить PRO", callback_data="tariff_cancel_pro")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])

def get_tariff_duration_kb(selected_days: int = None) -> InlineKeyboardMarkup:
    price_stars = {1: 10, 7: 55, 15: 100, 30: 175, 60: 300, 90: 450}
    buttons = []
    row = []
    for days in [1, 7, 15]:
        row.append(InlineKeyboardButton(text=f"{days} дн.", callback_data=f"tariff_duration_{days}"))
    buttons.append(row)
    row = []
    for days in [30, 60, 90]:
        row.append(InlineKeyboardButton(text=f"{days} дн.", callback_data=f"tariff_duration_{days}"))
    buttons.append(row)
    if selected_days is not None:
        price = price_stars.get(selected_days, 0)
        buttons.append([InlineKeyboardButton(text=f"💰 Купить ({selected_days} дн.) – {price} ⭐", callback_data=f"tariff_buy_stars_{selected_days}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tariff_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_tariff_payment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tariff_duration")]
    ])

def get_help_kb(support_link: str = None) -> InlineKeyboardMarkup:
    url = support_link or "https://t.me/your_support_bot"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆘 Поддержка", url=url)],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="go_to_instruction")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])

def get_instruction_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Запуск", callback_data="instruction_page_1")],
        [InlineKeyboardButton(text="🛡 Безопасность", callback_data="instruction_page_2")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])

def get_instruction_page_1_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Далее", callback_data="instruction_page_2")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="back_to_instruction_main")]
    ])

def get_instruction_page_2_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="instruction_page_1")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="back_to_instruction_main")]
    ])

def get_accounts_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить профиль", callback_data="add_profile")],
        [InlineKeyboardButton(text="🗑 Удалить профиль", callback_data="delete_profile")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])

def get_login_method_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📲 По SMS", callback_data="sms_login")],
        [InlineKeyboardButton(text="📷 По QR-коду", callback_data="qr_login")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_accounts")]
    ])

def get_code_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ Подсказка", callback_data="code_hint")],
        [InlineKeyboardButton(text="🔄 Повторить", callback_data="retry_phone")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_accounts")]
    ])

def get_confirm_delete_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_delete_yes"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="confirm_delete_no")]
    ])

def get_cancel_2fa_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_accounts")]
    ])

def get_phone_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер", request_contact=True)],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def get_schedule_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Завтра 10:00", callback_data="schedule_tomorrow_10")],
        [InlineKeyboardButton(text="📅 Завтра 15:00", callback_data="schedule_tomorrow_15")],
        [InlineKeyboardButton(text="📅 Послезавтра 10:00", callback_data="schedule_dayafter_10")],
        [InlineKeyboardButton(text="🕒 Своё время", callback_data="schedule_custom")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_panel")]
    ])

def build_groups_inline(groups_list: list, page: int = 0, per_page: int = 9) -> InlineKeyboardMarkup:
    total = len(groups_list)
    start = page * per_page
    end = min(start + per_page, total)
    buttons = []
    row = []
    for idx, group in enumerate(groups_list[start:end]):
        text = f"{group.get('title', 'Без названия')} 👥 {group.get('participants_count', 0)}"
        callback_data = f"add_group_{group.get('id')}"
        row.append(InlineKeyboardButton(text=text, callback_data=callback_data))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"groups_page_{page-1}"))
    if end < total:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"groups_page_{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    action_buttons = [
        InlineKeyboardButton(text="✅ Сохранить", callback_data="save_groups"),
        InlineKeyboardButton(text="📌 Выбрать все", callback_data="select_all_groups")
    ]

    buttons.append(action_buttons)
    return InlineKeyboardMarkup(inline_keyboard=buttons)