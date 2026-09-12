import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.scheduler import job_open_reminder, job_pre_close_reminder
from bot.utils import group_report_text


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
        self.bot.get_me.return_value = SimpleNamespace(username="daily_report_bot")

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


if __name__ == "__main__":
    unittest.main()
