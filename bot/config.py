import datetime
import os
import re
from dataclasses import dataclass
from pathlib import Path

import pytz
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class Config:
    bot_token: str
    default_timezone: str
    database_path: str
    reminder_time: str


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "BOT_TOKEN не задан. Скопируйте .env.example в .env и укажите токен от @BotFather."
        )
    reminder_time = os.getenv("REMINDER_TIME", "20:00").strip()
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", reminder_time):
        raise RuntimeError(
            "REMINDER_TIME должен быть указан в формате ЧЧ:ММ, например 20:00."
        )

    default_timezone = os.getenv("DEFAULT_TIMEZONE", "Asia/Bishkek").strip()
    try:
        pytz.timezone(default_timezone)
    except pytz.UnknownTimeZoneError as error:
        raise RuntimeError(
            f"DEFAULT_TIMEZONE содержит неизвестный часовой пояс: {default_timezone}"
        ) from error

    database_path = Path(os.getenv("DATABASE_PATH", "bot/daily_report_bot.db"))
    if not database_path.is_absolute():
        database_path = PROJECT_ROOT / database_path

    return Config(
        bot_token=token,
        default_timezone=default_timezone,
        database_path=str(database_path),
        reminder_time=reminder_time,
    )
