import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch

from bot.database import Database
from bot.handlers.group_admin import cmd_connect
from bot.handlers.standup import send_report
from bot.scheduler import job_open_reminder, job_pre_close_reminder, job_summary


GROUP_ID = -100123
THREAD_ID = 41


class DatabaseTopicBindingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.db_path = Path(self.temp_dir.name) / "bot.db"

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_new_database_stores_selected_topic(self):
        db = Database(str(self.db_path))
        await db.connect()

        await db.upsert_group(GROUP_ID, "Team", "Asia/Almaty", THREAD_ID)

        group = await db.get_group(GROUP_ID)
        self.assertEqual(group["thread_id"], THREAD_ID)
        await db.close()

    async def test_existing_database_is_migrated_without_losing_group(self):
        connection = sqlite3.connect(self.db_path)
        connection.execute(
            "CREATE TABLE groups ("
            "group_id INTEGER PRIMARY KEY, title TEXT, connected INTEGER NOT NULL DEFAULT 1, "
            "window_start TEXT NOT NULL DEFAULT '18:00', "
            "window_end TEXT NOT NULL DEFAULT '21:00', "
            "timezone TEXT NOT NULL DEFAULT 'Asia/Bishkek')"
        )
        connection.execute(
            "INSERT INTO groups (group_id, title, timezone) VALUES (?, ?, ?)",
            (GROUP_ID, "Existing Team", "Asia/Almaty"),
        )
        connection.commit()
        connection.close()

        db = Database(str(self.db_path))
        await db.connect()

        group = await db.get_group(GROUP_ID)
        self.assertEqual(group["title"], "Existing Team")
        self.assertIsNone(group["thread_id"])
        await db.close()


class ConnectTopicBindingTests(unittest.IsolatedAsyncioTestCase):
    async def test_connect_saves_topic_where_command_was_sent(self):
        message = SimpleNamespace(
            chat=SimpleNamespace(id=GROUP_ID, title="Team"),
            from_user=SimpleNamespace(id=7, username="admin", full_name="Admin"),
            message_thread_id=THREAD_ID,
            answer=AsyncMock(),
            reply=AsyncMock(),
        )
        db = AsyncMock()
        db.get_group.return_value = {
            "group_id": GROUP_ID,
            "timezone": "Asia/Almaty",
            "window_start": "18:00",
            "window_end": "21:00",
            "thread_id": THREAD_ID,
        }
        config = SimpleNamespace(default_timezone="Asia/Almaty")
        bot = AsyncMock()
        bot.get_chat_member.return_value = SimpleNamespace(status="administrator")

        with patch("bot.handlers.group_admin.schedule_group_jobs"):
            await cmd_connect(message, db, config, bot, SimpleNamespace())

        db.upsert_group.assert_awaited_once_with(
            group_id=GROUP_ID,
            title="Team",
            timezone="Asia/Almaty",
            thread_id=THREAD_ID,
        )


class TopicDestinationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.group = {
            "group_id": GROUP_ID,
            "connected": 1,
            "timezone": "Asia/Almaty",
            "window_start": "18:00",
            "window_end": "21:00",
            "thread_id": THREAD_ID,
        }

    async def test_submitted_report_is_published_in_selected_topic(self):
        callback = SimpleNamespace(
            from_user=SimpleNamespace(id=7, full_name="Employee"),
            message=SimpleNamespace(edit_reply_markup=AsyncMock(), answer=AsyncMock()),
            answer=AsyncMock(),
        )
        state = AsyncMock()
        state.get_data.return_value = {
            "group_id": GROUP_ID,
            "report_date": "2026-09-09",
            "today_text": "Done",
            "tomorrow_text": "Next",
        }
        db = AsyncMock()
        db.get_group.return_value = self.group
        bot = AsyncMock()

        await send_report(callback, state, db, bot)

        bot.send_message.assert_awaited_once_with(
            GROUP_ID,
            ANY,
            message_thread_id=THREAD_ID,
        )

    async def test_all_scheduled_messages_use_selected_topic(self):
        db = AsyncMock()
        db.get_group.return_value = self.group
        db.get_members.return_value = [
            {"user_id": 7, "username": "employee", "full_name": "Employee"}
        ]
        db.get_submitted_user_ids.return_value = set()
        bot = AsyncMock()

        await job_open_reminder(bot, db, GROUP_ID)
        self.assertEqual(bot.send_message.await_args.kwargs["message_thread_id"], THREAD_ID)

        bot.send_message.reset_mock()
        await job_pre_close_reminder(bot, db, GROUP_ID)
        self.assertEqual(bot.send_message.await_args.kwargs["message_thread_id"], THREAD_ID)

        bot.send_message.reset_mock()
        await job_summary(bot, db, GROUP_ID)
        self.assertEqual(bot.send_message.await_args.kwargs["message_thread_id"], THREAD_ID)

    async def test_general_chat_uses_no_topic_id(self):
        group = dict(self.group, thread_id=None)
        db = AsyncMock()
        db.get_group.return_value = group
        bot = AsyncMock()

        await job_open_reminder(bot, db, GROUP_ID)

        self.assertIsNone(bot.send_message.await_args.kwargs["message_thread_id"])


if __name__ == "__main__":
    unittest.main()
