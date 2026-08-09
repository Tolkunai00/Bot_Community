import datetime
import pytz
from aiosqlite import Row


def parse_hhmm(value: str) -> datetime.time:
    hour, minute = value.split(":")
    return datetime.time(hour=int(hour), minute=int(minute))


def now_in_tz(timezone: str) -> datetime.datetime:
    tz = pytz.timezone(timezone)
    return datetime.datetime.now(tz)


def window_status(group_row: Row) -> str:
    tz = group_row["timezone"]
    now = now_in_tz(tz).time()
    start = parse_hhmm(group_row["window_start"])
    end = parse_hhmm(group_row["window_end"])

    if now < start:
        return "too_early"
    if now > end:
        return "closed"
    return "open"


def format_mention(user_id: int, username: str | None, full_name: str) -> str:
    if username:
        return f"@{username}"
    return f'<a href="tg://user?id={user_id}">{full_name}</a>'


def report_preview_text(full_name: str, today_text: str, tomorrow_text: str) -> str:
    return (
        "📋 <b>Проверьте отчёт</b>\n"
        f"👤 {full_name}\n\n"
        "📅 <b>Сегодня</b>\n"
        f"{to_bullets(today_text)}\n\n"
        "📅 <b>Завтра</b>\n"
        f"{to_bullets(tomorrow_text)}"
    )


def group_report_text(full_name: str, today_text: str, tomorrow_text: str, time_str: str) -> str:
    return (
        "📋 <b>Новый ежедневный отчёт</b>\n"
        f"👤 {full_name}\n\n"
        "📅 <b>Сегодня</b>\n"
        f"{to_bullets(today_text)}\n\n"
        "📅 <b>Завтра</b>\n"
        f"{to_bullets(tomorrow_text)}\n\n"
        f"🕕 Время: {time_str}"
    )


def to_bullets(text: str) -> str:
    lines = [line.strip() for line in text.replace(",", "\n").splitlines() if line.strip()]
    if not lines:
        lines = [text.strip()]
    return "\n".join(f"• {line}" for line in lines)
