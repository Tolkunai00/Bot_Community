from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.config import Config
from bot.database import Database
from bot.scheduler import schedule_group_jobs, unschedule_group_jobs
from bot.utils import now_in_tz, parse_hhmm

router = Router(name="group_admin")

GROUP_TYPES = {ChatType.GROUP, ChatType.SUPERGROUP}


async def _is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in ("administrator", "creator")


@router.message(Command("connect"), F.chat.type.in_(GROUP_TYPES))
async def cmd_connect(message: Message, db: Database, config: Config, bot: Bot, scheduler: AsyncIOScheduler):
    if not await _is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("🚫 Подключить группу может только администратор группы.")
        return

    await db.upsert_group(
        group_id=message.chat.id,
        title=message.chat.title or "Группа",
        timezone=config.default_timezone,
    )
    await db.upsert_member(
        message.chat.id, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    group = await db.get_group(message.chat.id)
    schedule_group_jobs(scheduler, bot, db, group)

    await message.answer(
        "✅ Группа подключена к боту.\n\n"
        "Ежедневные отчёты сотрудников будут публиковаться здесь.\n"
        "Время приёма отчётов по умолчанию: 18:00 — 21:00.\n\n"
        "Проверить статус: /status"
    )


@router.message(Command("disconnect"), F.chat.type.in_(GROUP_TYPES))
async def cmd_disconnect(message: Message, db: Database, bot: Bot, scheduler: AsyncIOScheduler):
    if not await _is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("🚫 Отключить группу может только администратор группы.")
        return

    await db.set_group_connected(message.chat.id, connected=False)
    unschedule_group_jobs(scheduler, message.chat.id)
    await message.answer("🔌 Группа отключена от бота. Приём отчётов для неё остановлен.")


@router.message(Command("status"), F.chat.type.in_(GROUP_TYPES))
async def cmd_status(message: Message, db: Database):
    group = await db.get_group(message.chat.id)
    if not group or not group["connected"]:
        await message.answer(
            "🔌 Эта группа не подключена к боту.\nИспользуйте /connect, чтобы подключить."
        )
        return

    member_count = await db.get_member_count(message.chat.id)
    now = now_in_tz(group["timezone"])
    start = group["window_start"]
    end = group["window_end"]

    if now.time() < parse_hhmm(start):
        next_event = f"открытие приёма отчётов сегодня в {start}"
    elif now.time() <= parse_hhmm(end):
        next_event = f"закрытие приёма отчётов сегодня в {end}"
    else:
        next_event = f"открытие приёма отчётов завтра в {start}"

    await message.answer(
        "📊 <b>Статус группы</b>\n\n"
        "Подключение: ✅ подключена\n"
        f"Участников на учёте: {member_count}\n"
        f"Время приёма отчётов: {start} — {end}\n"
        f"Часовой пояс: {group['timezone']}\n"
        f"Ближайшее событие: {next_event}"
    )


@router.message(F.chat.type.in_(GROUP_TYPES))
async def track_group_activity(message: Message, db: Database):
    if message.from_user and not message.from_user.is_bot:
        group = await db.get_group(message.chat.id)
        if group and group["connected"]:
            await db.upsert_member(
                message.chat.id,
                message.from_user.id,
                message.from_user.username,
                message.from_user.full_name,
            )


@router.chat_member()
async def track_membership_changes(event: ChatMemberUpdated, db: Database):
    group = await db.get_group(event.chat.id)
    if not group or not group["connected"]:
        return

    new_status = event.new_chat_member.status
    user = event.new_chat_member.user
    if new_status in ("member", "administrator", "creator"):
        await db.upsert_member(event.chat.id, user.id, user.username, user.full_name)
    elif new_status in ("left", "kicked"):
        await db.remove_member(event.chat.id, user.id)
