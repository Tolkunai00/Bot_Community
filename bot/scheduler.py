import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from bot.database import Database, today_str
from bot.utils import format_mention, now_in_tz, parse_hhmm

logger = logging.getLogger(__name__)


async def _telegram_call(operation, attempts: int = 3):
    delay = 2.0
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except TelegramNetworkError as error:
            if attempt == attempts:
                logger.error("Telegram API недоступен после %d попыток: %s", attempts, error)
                return None
            logger.warning(
                "Telegram API временно недоступен, попытка %d/%d: %s",
                attempt,
                attempts,
                error,
            )
            await asyncio.sleep(delay)
            delay *= 2
        except TelegramAPIError as error:
            logger.error("Telegram отклонил запланированное сообщение: %s", error)
            return None


async def _send_message(bot: Bot, *args, **kwargs) -> bool:
    async def send():
        await bot.send_message(*args, **kwargs)
        return True

    return bool(await _telegram_call(send))


async def _bot_link(bot: Bot) -> str:
    bot_user = await _telegram_call(bot.me)
    if not bot_user:
        return ""
    return f"https://t.me/{bot_user.username}"


async def job_open_reminder(bot: Bot, db: Database, group_id: int):
    group = await db.get_group(group_id)
    if not group or not group["connected"]:
        return
    bot_link = await _bot_link(bot)
    if not bot_link:
        return
    await _send_message(
        bot,
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
    if not bot_link:
        return
    mentions = " ".join(
        format_mention(m["user_id"], m["username"], m["full_name"]) for m in pending
    )
    await _send_message(
        bot,
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
        await _send_message(
            bot,
            group_id,
            "🎉 Отлично!\n\nСегодня все участники успешно отправили ежедневный отчёт.",
            message_thread_id=group["thread_id"],
        )
        return

    names = "\n".join(
        f"• {format_mention(m['user_id'], m['username'], m['full_name'])}"
        for m in pending
    )
    await _send_message(
        bot,
        group_id,
        "📊 <b>Итоги дня</b>\n\n"
        f"✅ Отправили отчёт: {len(submitted)}\n\n"
        f"❌ Не отправили:\n{names}",
        parse_mode="HTML",
        message_thread_id=group["thread_id"],
    )


def schedule_group_jobs(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    db: Database,
    group_row,
    reminder_time: str = "20:00",
) -> None:
    group_id = group_row["group_id"]
    tz = group_row["timezone"]
    start = parse_hhmm(group_row["window_start"])
    end = parse_hhmm(group_row["window_end"])
    reminder = parse_hhmm(reminder_time)

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
        CronTrigger(hour=reminder.hour, minute=reminder.minute, timezone=tz),
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


async def setup_scheduler(bot: Bot, db: Database, reminder_time: str) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(
        timezone=pytz.UTC,
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 300,
        },
    )
    groups = await db.get_connected_groups()
    for group in groups:
        schedule_group_jobs(scheduler, bot, db, group, reminder_time)
    scheduler.start()
    return scheduler
