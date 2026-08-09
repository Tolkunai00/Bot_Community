from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.database import Database, today_str
from bot.keyboards import preview_keyboard
from bot.states import StandupStates
from bot.utils import (group_report_text, now_in_tz, report_preview_text, window_status,)

router = Router(name="standup")

UNSUPPORTED_REPLIES = {
    "photo": "📷\n\nИзвините.\nЯ принимаю только текстовые сообщения.\n\nПожалуйста, используйте команду /standup",
    "video": "🎥\n\nВидео не поддерживаются.\nЯ принимаю только текстовые ответы.",
    "voice": "🎤\n\nГолосовые сообщения пока не поддерживаются.\n\nПожалуйста, отправьте текстовый ответ.",
    "sticker": "🙂\n\nЯ не умею обрабатывать стикеры.\nИспользуйте текстовые сообщения.",
    "document": "📄\n\nЯ принимаю только текстовые сообщения.",
}


def _unsupported_reply(message: Message) -> str:
    if message.photo:
        return UNSUPPORTED_REPLIES["photo"]
    if message.video:
        return UNSUPPORTED_REPLIES["video"]
    if message.voice or message.audio:
        return UNSUPPORTED_REPLIES["voice"]
    if message.sticker:
        return UNSUPPORTED_REPLIES["sticker"]
    if message.document:
        return UNSUPPORTED_REPLIES["document"]
    return "Пожалуйста, отправьте ответ текстовым сообщением."


@router.message(Command("standup"), F.chat.type == ChatType.PRIVATE)
async def cmd_standup(message: Message, state: FSMContext, db: Database):
    group_id = await db.find_user_group(message.from_user.id)
    if group_id is None:
        await message.answer(
            "Я пока не знаю, к какой команде вас отнести.\n\n"
            "Попросите администратора подключить группу через /connect и напишите "
            "что-нибудь в общем чате команды — тогда бот вас увидит."
        )
        return

    group = await db.get_group(group_id)
    status = window_status(group)

    if status == "too_early":
        await message.answer(
            "⏰ Приём отчётов ещё не начался.\n\n"
            f"Отправить отчёт можно ежедневно с {group['window_start']} до {group['window_end']}.\n\n"
            "Пожалуйста, попробуйте позже."
        )
        return

    if status == "closed":
        await message.answer(
            "🔒 Приём отчётов уже завершён.\n\n"
            "Сегодня отправить отчёт уже нельзя.\n\n"
            f"Следующее окно приёма отчётов откроется завтра в {group['window_start']}."
        )
        return

    date_str = today_str(now_in_tz(group["timezone"]).tzinfo)
    existing = await db.get_today_report(group_id, message.from_user.id, date_str)
    if existing and existing["status"] == "submitted":
        await message.answer("Сегодня вы уже отправили отчёт.\n\nСпасибо!")
        return

    await state.set_state(StandupStates.waiting_today)
    await state.update_data(group_id=group_id, report_date=date_str)
    await message.answer(
        "Что вы сделали сегодня?\n\nОпишите выполненную работу максимально подробно."
    )


@router.message(StandupStates.waiting_today, F.text)
async def process_today(message: Message, state: FSMContext):
    await state.update_data(today_text=message.text)
    await state.set_state(StandupStates.waiting_tomorrow)
    await message.answer(
        "Что вы планируете сделать завтра?\n\nОпишите задачи на следующий рабочий день."
    )


@router.message(StandupStates.waiting_today)
async def reject_today_non_text(message: Message):
    await message.answer(_unsupported_reply(message))


@router.message(StandupStates.waiting_tomorrow, F.text)
async def process_tomorrow(message: Message, state: FSMContext, db: Database):
    data = await state.update_data(tomorrow_text=message.text)

    await db.save_draft(
        group_id=data["group_id"],
        user_id=message.from_user.id,
        report_date=data["report_date"],
        today_text=data["today_text"],
        tomorrow_text=data["tomorrow_text"],
    )

    await state.set_state(StandupStates.preview)
    text = report_preview_text(message.from_user.full_name, data["today_text"], data["tomorrow_text"])
    await message.answer(text, reply_markup=preview_keyboard())


@router.message(StandupStates.waiting_tomorrow)
async def reject_tomorrow_non_text(message: Message):
    await message.answer(_unsupported_reply(message))


@router.callback_query(StandupStates.preview, F.data == "standup:edit")
async def edit_report(callback: CallbackQuery, state: FSMContext):
    await state.set_state(StandupStates.waiting_today)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Что вы сделали сегодня?\n\nОпишите выполненную работу максимально подробно."
    )
    await callback.answer()


@router.callback_query(StandupStates.preview, F.data == "standup:send")
async def send_report(callback: CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    data = await state.get_data()
    group_id = data["group_id"]
    report_date = data["report_date"]

    group = await db.get_group(group_id)
    now = now_in_tz(group["timezone"])
    submitted_at = now.strftime("%Y-%m-%d %H:%M:%S")

    await db.submit_report(group_id, callback.from_user.id, report_date, submitted_at)

    group_text = group_report_text(
        callback.from_user.full_name,
        data["today_text"],
        data["tomorrow_text"],
        now.strftime("%H:%M"),
    )
    await bot.send_message(group_id, group_text)

    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("✅ Отчёт успешно отправлен.\n\nСпасибо!")
    await callback.answer()


@router.message(Command("myreport"), F.chat.type == ChatType.PRIVATE)
async def cmd_myreport(message: Message, db: Database):
    group_id = await db.find_user_group(message.from_user.id)
    if group_id is None:
        await message.answer("Вы пока не привязаны ни к одной группе.")
        return

    group = await db.get_group(group_id)
    date_str = today_str(now_in_tz(group["timezone"]).tzinfo)
    report = await db.get_today_report(group_id, message.from_user.id, date_str)

    if not report or report["status"] != "submitted":
        await message.answer(
            "Вы ещё не отправили отчёт сегодня.\n\nИспользуйте /standup, чтобы отправить."
        )
        return

    await message.answer(
        "📋 <b>Ваш сегодняшний отчёт</b>\n\n"
        f"📅 Сегодня\n{report['today_text']}\n\n"
        f"📅 Завтра\n{report['tomorrow_text']}\n\n"
        "Статус: ✅ Отправлен"
    )
