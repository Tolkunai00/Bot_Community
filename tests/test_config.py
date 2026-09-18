import os
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.config import PROJECT_ROOT, load_config


class ConfigTests(unittest.TestCase):
    def test_default_timezone_is_bishkek(self):
        with patch.dict(
            os.environ,
            {"BOT_TOKEN": "123456:test-token"},
            clear=True,
        ):
            config = load_config()

        self.assertEqual(config.default_timezone, "Asia/Bishkek")

    def test_reminder_time_can_be_set_from_environment(self):
        with patch.dict(
            os.environ,
            {
                "BOT_TOKEN": "123456:test-token",
                "REMINDER_TIME": "20:20",
            },
            clear=True,
        ):
            config = load_config()

        self.assertEqual(config.reminder_time, "20:20")

    def test_invalid_reminder_time_is_rejected_at_startup(self):
        with patch.dict(
            os.environ,
            {
                "BOT_TOKEN": "123456:test-token",
                "REMINDER_TIME": "25:99",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "REMINDER_TIME"):
                load_config()

    def test_reminder_time_must_use_exact_hour_and_minute_format(self):
        with patch.dict(
            os.environ,
            {
                "BOT_TOKEN": "123456:test-token",
                "REMINDER_TIME": "20:00:30",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "REMINDER_TIME"):
                load_config()

    def test_invalid_timezone_is_rejected_at_startup(self):
        with patch.dict(
            os.environ,
            {
                "BOT_TOKEN": "123456:test-token",
                "DEFAULT_TIMEZONE": "Invalid/Timezone",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "DEFAULT_TIMEZONE"):
                load_config()

    def test_relative_database_path_is_resolved_from_project_root(self):
        with patch.dict(
            os.environ,
            {
                "BOT_TOKEN": "123456:test-token",
                "DATABASE_PATH": "data/bot.db",
            },
            clear=True,
        ):
            config = load_config()

        self.assertEqual(Path(config.database_path), PROJECT_ROOT / "data" / "bot.db")
