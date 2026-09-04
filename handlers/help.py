from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from keyboards import get_help_kb, get_instruction_main_kb, main_menu_kb
from config import SUPPORT_LINK

router = Router()

@router.message(F.text == "❓ Помощь")
async def help_command(message: Message):
    text = (
        "🆘 <b>Помощь</b>\n\n"
        "Наши официальные точки связи\n\n"
        "❓ <b>Частые вопросы</b>\n\n"
        "<b>Мой аккаунт в безопасности?</b>\n"
        "Да. Сессия используется только для вашей авторассылки — личная переписка не читается и не сохраняется.\n\n"
        "<b>Почему сообщение не дошло в группу?</b>\n"
        "Чаще всего в группе slowmode, запрет на отправку или аккаунт временно ограничен. Раздел «Статистика» показывает причину.\n\n"
        "<b>Авторассылка сама остановилась?</b>\n"
        "Бот останавливает её ради безопасности: причина пишется в статистике. Устраните причину и включите снова.\n\n"
        "<b>Что даёт PRO?</b>\n"
        "Убирается подпись бота, снимаются дневной и групповой лимиты, можно подключить до 5 аккаунтов.\n\n"
        "Не нашли ответ? Напишите в поддержку — обращения рассматриваются в рабочее время."
    )
    kb = get_help_kb(support_link=SUPPORT_LINK)
    await message.answer(text, reply_markup=kb)

@router.callback_query(lambda c: c.data == "go_to_instruction")
async def go_to_instruction_from_help(callback: CallbackQuery):
    await callback.answer()
    text = (
        "📖 <b>Инструкции</b>\n\n"
        "Как правильно пользоваться ботом\n\n"
        "Выберите нужный раздел 👇"
    )
    await callback.message.edit_text(text, reply_markup=get_instruction_main_kb())

@router.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main_from_help(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("⬅️ Возврат в главное меню.")
    await callback.message.answer("Выберите раздел 👇", reply_markup=main_menu_kb)