import datetime
from html import escape

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
    if now >= end:
        return "closed"
    return "open"


def format_mention(user_id: int, username: str | None, full_name: str) -> str:
    if username:
        return f"@{username}"
    return f'<a href="tg://user?id={user_id}">{escape(full_name)}</a>'


def report_preview_text(full_name: str, today_text: str, tomorrow_text: str) -> str:
    return (
        "📋 <b>Проверьте отчёт</b>\n"
        f"👤 {escape(full_name)}\n\n"
        "📅 <b>Сегодня</b>\n"
        f"{to_bullets(today_text)}\n\n"
        "📅 <b>Завтра</b>\n"
        f"{to_bullets(tomorrow_text)}"
    )


def group_report_text(
    user_id: int,
    full_name: str,
    report_date: str,
    today_text: str,
    tomorrow_text: str,
    time_str: str,
) -> str:
    display_date = datetime.date.fromisoformat(report_date).strftime("%d.%m.%Y")
    author_link = f'<a href="tg://user?id={user_id}">{escape(full_name)}</a>'
    return (
        f"📅 {display_date}\n\n"
        "━━━━━━━━━━━━\n"
        "👤 <b>АВТОР ОТЧЁТА</b>\n"
        f"🔥 <b>{author_link}</b>\n"
        "━━━━━━━━━━━━\n\n"
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
    return "\n".join(f"• {escape(line)}" for line in lines)
