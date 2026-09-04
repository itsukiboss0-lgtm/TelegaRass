from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from keyboards import get_instruction_main_kb, get_instruction_page_1_kb, get_instruction_page_2_kb, main_menu_kb

router = Router()

@router.message(F.text == "📖 Инструкция")
async def instruction_main(message: Message):
    text = (
        "📖 <b>Инструкции</b>\n\n"
        "Как правильно пользоваться ботом\n\n"
        "Выберите нужный раздел 👇"
    )
    await message.answer(text, reply_markup=get_instruction_main_kb())

@router.callback_query(lambda c: c.data == "instruction_page_1")
async def instruction_page_1(callback: CallbackQuery):
    await callback.answer()
    text = (
        "🚀 <b>Запуск авторассылки</b>\n"
        "Быстрый старт · 1/2\n"
        "─────────────────────\n"
        "Авторассылка автоматически отправляет выбранное сообщение в указанные группы — для анонсов, рекламы или повторных сообщений. Настраиваете один раз, аккаунт отправляет сам.\n\n"
        "📌 <b>Шаги</b>\n\n"
        "1️⃣ В разделе «Профили» выберите аккаунт или подключите новый.\n"
        "   │\n"
        "2️⃣ «Настройка групп» — отметьте группы для отправки.\n"
        "   │\n"
        "3️⃣ «Текст сообщения» — выберите «Обычное» или «Разные» (2–4 варианта) и отправьте сообщение боту.\n"
        "   │\n"
        "4️⃣ «Интервал» — настройте паузу между циклами.\n"
        "   │\n"
        "5️⃣ «Авто рассылка» → нажмите «Запустить».\n\n"
        "💡 <b>Перед большой рассылкой</b>\n\n"
        "Сначала отправьте пробное сообщение в одну группу — так легко проверить текст, медиа и вид."
    )
    await callback.message.edit_text(text, reply_markup=get_instruction_page_1_kb())

@router.callback_query(lambda c: c.data == "instruction_page_2")
async def instruction_page_2(callback: CallbackQuery):
    await callback.answer()
    text = (
        "🛡 <b>Снизить риск блокировки</b>\n"
        "Безопасность · 2/2\n"
        "─────────────────────\n"
        "Telegram может ограничить аккаунт из-за резкой активности, одинаковых сообщений и жалоб. Начинайте отправку постепенно и следите за реакцией.\n\n"
        "📌 <b>Шаги</b>\n\n"
        "1️⃣ Не используйте новый аккаунт сразу для больших рассылок.\n"
        "   │\n"
        "2️⃣ Оставляйте достаточные паузы между группами; не шлите одно и то же подряд — используйте «Разные» варианты.\n"
        "   │\n"
        "3️⃣ Используйте стабильный интернет; не разрывайте сессию часто.\n"
        "   │\n"
        "4️⃣ При ошибках отправки или ограничениях Telegram остановите рассылку.\n\n"
        "💡 <b>Главное правило</b>\n\n"
        "Ровный и спокойный темп обычно безопаснее короткой резкой активности."
    )
    await callback.message.edit_text(text, reply_markup=get_instruction_page_2_kb())

@router.callback_query(lambda c: c.data == "back_to_instruction_main")
async def back_to_instruction_main(callback: CallbackQuery):
    await callback.answer()
    text = (
        "📖 <b>Инструкции</b>\n\n"
        "Как правильно пользоваться ботом\n\n"
        "Выберите нужный раздел 👇"
    )
    await callback.message.edit_text(text, reply_markup=get_instruction_main_kb())

@router.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main_from_instruction(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("⬅️ Возврат в главное меню.")
    await callback.message.answer("Выберите раздел 👇", reply_markup=main_menu_kb)