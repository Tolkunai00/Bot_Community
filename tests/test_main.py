import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import GetMe

from bot.main import main, wait_for_telegram


class TelegramStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_temporary_network_error_is_retried(self):
        bot = AsyncMock()
        bot.me.side_effect = [
            TelegramNetworkError(method=GetMe(), message="offline"),
            SimpleNamespace(username="daily_report_bot"),
        ]

        with self.assertLogs("bot.main", level="WARNING"):
            with patch("bot.main.asyncio.sleep", new=AsyncMock()) as sleep:
                user = await wait_for_telegram(bot, retry_delay=0)

        self.assertEqual(user.username, "daily_report_bot")
        self.assertEqual(bot.me.await_count, 2)
        sleep.assert_awaited_once_with(0)

    async def test_scheduler_starts_before_waiting_for_telegram(self):
        events = []
        bot = AsyncMock()
        bot.session.close = AsyncMock()
        dispatcher = MagicMock()
        dispatcher.start_polling = AsyncMock()
        database = AsyncMock()
        scheduler = unittest.mock.Mock()

        async def setup(*args):
            events.append("scheduler")
            return scheduler

        async def wait(*args):
            events.append("telegram")

        config = SimpleNamespace(
            bot_token="123456:test-token",
            database_path="bot.db",
            reminder_time="20:00",
        )

        with patch("bot.main.load_config", return_value=config), patch(
            "bot.main.Bot", return_value=bot
        ), patch("bot.main.Dispatcher", return_value=dispatcher), patch(
            "bot.main.Database", return_value=database
        ), patch("bot.main.setup_scheduler", side_effect=setup), patch(
            "bot.main.wait_for_telegram", side_effect=wait
        ):
            await main()

        self.assertEqual(events, ["scheduler", "telegram"])
        scheduler.shutdown.assert_called_once_with(wait=False)
        database.close.assert_awaited_once()
        bot.session.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
