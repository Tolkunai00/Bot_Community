import datetime
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytz
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendMessage

from bot.scheduler import (
    job_open_reminder,
    job_pre_close_reminder,
    schedule_group_jobs,
    setup_scheduler,
)
from bot.utils import format_mention, group_report_text, window_status


GROUP_ID = -100123
THREAD_ID = 41


class GroupReportTextTests(unittest.TestCase):
    def test_report_starts_with_date_and_prominent_clickable_author(self):
        text = group_report_text(
            user_id=77,
            full_name="Alice <Lead>",
            report_date="2026-09-10",
            today_text="Done",
            tomorrow_text="Next",
            time_str="18:15",
        )

        self.assertTrue(text.startswith("📅 10.09.2026\n\n"))
        self.assertIn("━━━━━━━━━━━━\n👤 <b>АВТОР ОТЧЁТА</b>", text)
        self.assertIn(
            '🔥 <b><a href="tg://user?id=77">Alice &lt;Lead&gt;</a></b>',
            text,
        )
        self.assertIn("📅 <b>Сегодня</b>\n• Done", text)
        self.assertIn("📅 <b>Завтра</b>\n• Next", text)
        self.assertTrue(text.endswith("🕕 Время: 18:15"))

    def test_user_supplied_html_is_escaped(self):
        text = group_report_text(
            user_id=77,
            full_name="Alice <Lead>",
            report_date="2026-09-10",
            today_text="Fixed <critical>",
            tomorrow_text="Check A & B",
            time_str="18:15",
        )

        self.assertIn("• Fixed &lt;critical&gt;", text)
        self.assertIn("• Check A &amp; B", text)
        self.assertEqual(
            format_mention(77, None, "Alice <Lead>"),
            '<a href="tg://user?id=77">Alice &lt;Lead&gt;</a>',
        )


class WindowStatusTests(unittest.TestCase):
    def test_window_is_closed_at_exact_end_time(self):
        group = {
            "timezone": "Asia/Almaty",
            "window_start": "18:00",
            "window_end": "21:00",
        }
        exact_end = datetime.datetime(2026, 9, 13, 21, 0, tzinfo=pytz.UTC)

        with patch("bot.utils.now_in_tz", return_value=exact_end):
            self.assertEqual(window_status(group), "closed")


class ScheduleTests(unittest.IsolatedAsyncioTestCase):
    def test_reminder_is_scheduled_for_configured_time(self):
        scheduler = unittest.mock.Mock()
        group = {
            "group_id": GROUP_ID,
            "timezone": "Asia/Bishkek",
            "window_start": "18:00",
            "window_end": "21:00",
        }

        schedule_group_jobs(scheduler, unittest.mock.Mock(), unittest.mock.Mock(), group, "20:00")

        open_trigger = scheduler.add_job.call_args_list[0].args[1]
        reminder_trigger = scheduler.add_job.call_args_list[1].args[1]
        summary_trigger = scheduler.add_job.call_args_list[2].args[1]
        self.assertIn("hour='18'", str(open_trigger))
        self.assertIn("minute='0'", str(open_trigger))
        self.assertIn("hour='20'", str(reminder_trigger))
        self.assertIn("minute='0'", str(reminder_trigger))
        self.assertIn("hour='21'", str(summary_trigger))
        self.assertIn("minute='0'", str(summary_trigger))
        self.assertEqual(str(open_trigger.timezone), "Asia/Bishkek")
        self.assertEqual(str(reminder_trigger.timezone), "Asia/Bishkek")
        self.assertEqual(str(summary_trigger.timezone), "Asia/Bishkek")

    async def test_scheduler_uses_explicit_utc_base_timezone(self):
        db = AsyncMock()
        db.get_connected_groups.return_value = []
        scheduler = await setup_scheduler(AsyncMock(), db, "20:00")
        self.addCleanup(scheduler.shutdown, False)

        self.assertEqual(str(scheduler.timezone), "UTC")


class ReminderTextTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.group = {
            "group_id": GROUP_ID,
            "connected": 1,
            "timezone": "Asia/Almaty",
            "window_start": "18:00",
            "window_end": "21:00",
            "thread_id": THREAD_ID,
        }
        self.db = AsyncMock()
        self.db.get_group.return_value = self.group
        self.bot = AsyncMock()
        self.bot.me.return_value = SimpleNamespace(username="daily_report_bot")

    async def test_open_reminder_has_no_all_and_explains_bot_flow(self):
        await job_open_reminder(self.bot, self.db, GROUP_ID)

        message = self.bot.send_message.await_args.args[1]
        self.assertNotIn("@all", message)
        self.assertIn("https://t.me/daily_report_bot", message)
        self.assertIn("Запустите бота", message)
        self.assertIn("/standup", message)
        self.assertEqual(
            self.bot.send_message.await_args.kwargs["message_thread_id"], THREAD_ID
        )

    async def test_pre_close_reminder_keeps_mentions_and_explains_bot_flow(self):
        self.db.get_members.return_value = [
            {"user_id": 7, "username": "employee", "full_name": "Employee"}
        ]
        self.db.get_submitted_user_ids.return_value = set()

        await job_pre_close_reminder(self.bot, self.db, GROUP_ID)

        message = self.bot.send_message.await_args.args[1]
        self.assertTrue(message.startswith("😂 <b>Ээээ, кетир отчёт!</b>\n\n"))
        self.assertIn("@employee", message)
        self.assertIn("https://t.me/daily_report_bot", message)
        self.assertIn("Запустите бота", message)
        self.assertIn("/standup", message)
        self.assertEqual(
            self.bot.send_message.await_args.kwargs["message_thread_id"], THREAD_ID
        )

    async def test_open_reminder_retries_temporary_telegram_failure(self):
        self.bot.send_message.side_effect = [
            TelegramNetworkError(method=SendMessage(chat_id=GROUP_ID, text="x"), message="offline"),
            None,
        ]

        with self.assertLogs("bot.scheduler", level="WARNING"):
            with patch("asyncio.sleep", new=AsyncMock()) as sleep:
                await job_open_reminder(self.bot, self.db, GROUP_ID)

        self.assertEqual(self.bot.send_message.await_count, 2)
        sleep.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
