import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    default_timezone: str
    database_path: str


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "BOT_TOKEN не задан. Скопируйте .env.example в .env и укажите токен от @BotFather."
        )
    return Config(
        bot_token=token,
        default_timezone=os.getenv("DEFAULT_TIMEZONE", "Asia/Bishkek"),
        database_path=os.getenv("DATABASE_PATH", "daily_report_bot.db"),
    )
