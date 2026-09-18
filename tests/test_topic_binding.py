import sqlite3
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch

from bot.database import Database
from bot.handlers.group_admin import cmd_connect
from bot.handlers.standup import process_today, process_tomorrow, send_report
from bot.scheduler import job_open_reminder, job_pre_close_reminder, job_summary


GROUP_ID = -100123
THREAD_ID = 41


class DatabaseTopicBindingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = Path.cwd() / f"test-{uuid.uuid4().hex}.db"
        self.db = None

    async def asyncTearDown(self):
        if self.db is not None:
            await self.db.close()
        self.db_path.unlink(missing_ok=True)

    async def test_new_database_stores_selected_topic(self):
        self.db = Database(str(self.db_path))
        await self.db.connect()

        await self.db.upsert_group(GROUP_ID, "Team", "Asia/Almaty", THREAD_ID)

        group = await self.db.get_group(GROUP_ID)
        self.assertEqual(group["thread_id"], THREAD_ID)
        self.assertEqual(group["window_start"], "18:00")

    async def test_existing_broken_window_start_is_repaired(self):
        connection = sqlite3.connect(self.db_path)
        connection.executescript(
            "CREATE TABLE groups ("
            "group_id INTEGER PRIMARY KEY, title TEXT, connected INTEGER NOT NULL DEFAULT 1, "
            "window_start TEXT NOT NULL, window_end TEXT NOT NULL DEFAULT '21:00', "
            "timezone TEXT NOT NULL DEFAULT 'Asia/Bishkek', thread_id INTEGER);"
            "CREATE TABLE members (group_id INTEGER, user_id INTEGER, username TEXT, "
            "full_name TEXT, PRIMARY KEY (group_id, user_id));"
            "CREATE TABLE reports (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER, "
            "user_id INTEGER, report_date TEXT, today_text TEXT, tomorrow_text TEXT, "
            "status TEXT DEFAULT 'draft', submitted_at TEXT, "
            "UNIQUE(group_id, user_id, report_date));"
        )
        connection.execute(
            "INSERT INTO groups (group_id, title, window_start) VALUES (?, ?, ?)",
            (GROUP_ID, "Team", "18:00\n    "),
        )
        connection.commit()
        connection.close()

        self.db = Database(str(self.db_path))
        await self.db.connect()

        group = await self.db.get_group(GROUP_ID)
        self.assertEqual(group["window_start"], "18:00")

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

        self.db = Database(str(self.db_path))
        await self.db.connect()

        group = await self.db.get_group(GROUP_ID)
        self.assertEqual(group["title"], "Existing Team")
        self.assertIsNone(group["thread_id"])

    async def test_failed_initialization_closes_partial_connection(self):
        connection = AsyncMock()
        connection.executescript.side_effect = sqlite3.DatabaseError("broken schema")
        db = Database(str(self.db_path))

        with patch("bot.database.aiosqlite.connect", new=AsyncMock(return_value=connection)):
            with self.assertRaisesRegex(sqlite3.DatabaseError, "broken schema"):
                await db.connect()

        connection.close.assert_awaited_once()
        self.assertIsNone(db._conn)

    async def test_close_is_idempotent(self):
        connection = AsyncMock()
        db = Database(str(self.db_path))
        db._conn = connection

        await db.close()
        await db.close()

        connection.close.assert_awaited_once()
        self.assertIsNone(db._conn)


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
        config = SimpleNamespace(default_timezone="Asia/Almaty", reminder_time="20:20")
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

    async def test_failed_publication_keeps_report_available_for_retry(self):
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
        bot.send_message.side_effect = RuntimeError("Telegram unavailable")

        with self.assertLogs("bot.handlers.standup", level="ERROR"):
            await send_report(callback, state, db, bot)

        db.submit_report.assert_not_awaited()
        state.clear.assert_not_awaited()
        callback.answer.assert_awaited_once_with(
            "Не удалось отправить отчёт. Попробуйте ещё раз.",
            show_alert=True,
        )

    async def test_stale_send_button_does_not_raise_key_error(self):
        callback = SimpleNamespace(answer=AsyncMock())
        state = AsyncMock()
        state.get_data.return_value = {}
        db = AsyncMock()
        bot = AsyncMock()

        await send_report(callback, state, db, bot)

        callback.answer.assert_awaited_once_with(
            "Черновик устарел. Запустите /standup ещё раз.",
            show_alert=True,
        )
        bot.send_message.assert_not_awaited()

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


class ReportInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_oversized_today_text_is_rejected_before_state_advance(self):
        message = SimpleNamespace(
            text="<" * 400,
            from_user=SimpleNamespace(id=7, full_name="Employee"),
            answer=AsyncMock(),
        )
        state = AsyncMock()

        await process_today(message, state)

        state.update_data.assert_not_awaited()
        state.set_state.assert_not_awaited()
        self.assertIn("слишком длинный", message.answer.await_args.args[0])

    async def test_oversized_tomorrow_text_is_not_saved(self):
        message = SimpleNamespace(
            text="<" * 400,
            from_user=SimpleNamespace(id=7, full_name="Employee"),
            answer=AsyncMock(),
        )
        state = AsyncMock()
        db = AsyncMock()

        await process_tomorrow(message, state, db)

        db.save_draft.assert_not_awaited()
        self.assertIn("слишком длинный", message.answer.await_args.args[0])


if __name__ == "__main__":
    unittest.main()
