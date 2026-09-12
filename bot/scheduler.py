import datetime
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bot.database import Database, today_str
from bot.utils import format_mention, now_in_tz, parse_hhmm


def _minus_one_hour(hhmm: str) -> tuple[int, int]:
    t = parse_hhmm(hhmm)
    dt = datetime.datetime.combine(datetime.date.today(), t) - datetime.timedelta(hours=1)
    return dt.hour, dt.minute


async def _bot_link(bot: Bot) -> str:
    bot_user = await bot.get_me()
    return f"https://t.me/{bot_user.username}"


async def job_open_reminder(bot: Bot, db: Database, group_id: int):
    group = await db.get_group(group_id)
    if not group or not group["connected"]:
        return
    bot_link = await _bot_link(bot)
    await bot.send_message(
        group_id,
        "🔔 Напоминание!\n\n"
        "Приём ежедневных отчётов открыт.\n"
        f"Пожалуйста, отправьте отчёт до {group['window_end']}.\n\n"
        f"🤖 Напишите отчёт боту: {bot_link}\n"
        "Запустите бота и начните заполнение командой /standup",
        message_thread_id=group["thread_id"],
    )


async def job_pre_close_reminder(bot: Bot, db: Database, group_id: int):
    group = await db.get_group(group_id)
    if not group or not group["connected"]:
        return

    date_str = today_str(now_in_tz(group["timezone"]).tzinfo)
    members = await db.get_members(group_id)
    submitted = await db.get_submitted_user_ids(group_id, date_str)
    pending = [m for m in members if m["user_id"] not in submitted]

    if not pending:
        return

    bot_link = await _bot_link(bot)
    mentions = " ".join(
        format_mention(m["user_id"], m["username"], m["full_name"]) for m in pending
    )
    await bot.send_message(
        group_id,
        "😂 <b>Ээээ, кетир отчёт!</b>\n\n"
        "🔔 Напоминание!\n"
        f"{mentions}\n"
        "Вы ещё не отправили сегодняшний отчёт.\n"
        "До окончания приёма осталось менее одного часа.\n\n"
        f"🤖 Напишите отчёт боту: {bot_link}\n"
        "Запустите бота и начните заполнение командой /standup",
        parse_mode="HTML",
        message_thread_id=group["thread_id"],
    )


async def job_summary(bot: Bot, db: Database, group_id: int):
    group = await db.get_group(group_id)
    if not group or not group["connected"]:
        return

    date_str = today_str(now_in_tz(group["timezone"]).tzinfo)
    members = await db.get_members(group_id)
    submitted = await db.get_submitted_user_ids(group_id, date_str)
    pending = [m for m in members if m["user_id"] not in submitted]

    if not pending:
        await bot.send_message(
            group_id,
            "🎉 Отлично!\n\nСегодня все участники успешно отправили ежедневный отчёт.",
            message_thread_id=group["thread_id"],
        )
        return

    names = "\n".join(f"• {m['full_name']}" for m in pending)
    await bot.send_message(
        group_id,
        "📊 <b>Итоги дня</b>\n\n"
        f"✅ Отправили отчёт: {len(submitted)}\n\n"
        f"❌ Не отправили:\n{names}",
        parse_mode="HTML",
        message_thread_id=group["thread_id"],
    )


def schedule_group_jobs(scheduler: AsyncIOScheduler, bot: Bot, db: Database, group_row) -> None:
    group_id = group_row["group_id"]
    tz = group_row["timezone"]
    start = parse_hhmm(group_row["window_start"])
    end = parse_hhmm(group_row["window_end"])
    pre_hour, pre_minute = _minus_one_hour(group_row["window_end"])

    prefix = f"group-{group_id}"

    scheduler.add_job(
        job_open_reminder,
        CronTrigger(hour=start.hour, minute=start.minute, timezone=tz),
        args=[bot, db, group_id],
        id=f"{prefix}-open",
        replace_existing=True,
    )
    scheduler.add_job(
        job_pre_close_reminder,
        CronTrigger(hour=pre_hour, minute=pre_minute, timezone=tz),
        args=[bot, db, group_id],
        id=f"{prefix}-pre-close",
        replace_existing=True,
    )
    scheduler.add_job(
        job_summary,
        CronTrigger(hour=end.hour, minute=end.minute, timezone=tz),
        args=[bot, db, group_id],
        id=f"{prefix}-summary",
        replace_existing=True,
    )


def unschedule_group_jobs(scheduler: AsyncIOScheduler, group_id: int) -> None:
    for suffix in ("open", "pre-close", "summary"):
        job_id = f"group-{group_id}-{suffix}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)


async def setup_scheduler(bot: Bot, db: Database) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    groups = await db.get_connected_groups()
    for group in groups:
        schedule_group_jobs(scheduler, bot, db, group)
    scheduler.start()
    return scheduler
