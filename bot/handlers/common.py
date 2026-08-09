import datetime
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.database import Database

router = Router(name="common")


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Добро пожаловать в Daily Report Bot!\n\n"
        "Этот бот помогает автоматически собирать ежедневные отчёты команды.\n\n"
        "🕕 Время приёма отчётов:\n18:00 — 21:00\n\n"
        "Для отправки отчёта используйте:\n/standup"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Как пользоваться ботом</b>\n\n"
        "/standup — отправить ежедневный отчёт (доступно с 18:00 до 21:00)\n"
        "/myreport — посмотреть уже отправленный сегодня отчёт\n"
        "/help — эта справка\n\n"
        "<b>Для владельца группы:</b>\n"
        "/connect — подключить группу к боту\n"
        "/disconnect — отключить группу\n"
        "/status — состояние подключения группы"
    )


@router.message(Command("ping"))
async def cmd_ping(message: Message, db: Database):
    db_ok = True
    try:
        await db.get_connected_groups()
    except Exception:
        db_ok = False

    now = datetime.datetime.now().strftime("%H:%M")
    await message.answer(
        "🟢 Бот работает.\n"
        f"База данных: {'OK' if db_ok else 'ОШИБКА'}\n"
        "Scheduler: OK\n\n"
        f"Текущее время: {now}"
    )
