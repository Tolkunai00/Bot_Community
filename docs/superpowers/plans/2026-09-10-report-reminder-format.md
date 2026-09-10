# Report and Reminder Formatting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the report date and a prominent clickable author block to published reports, remove `@all` from the opening reminder, and add the running bot's link plus `/standup` instructions to both reminders.

**Architecture:** Keep the existing message flow and scheduler intact. Extend the pure report formatter with the author ID and ISO report date, then have the existing send handler pass those values; update the two scheduler jobs to resolve the bot username through `bot.get_me()` and compose the required instructions.

**Tech Stack:** Python 3.12, aiogram 3.15, APScheduler 3.10, `unittest`/`unittest.mock`.

## Global Constraints

- Date format in a published report is exactly `ДД.ММ.ГГГГ`.
- The author name is bold, HTML-escaped, and linked through `tg://user?id=<user_id>`.
- The 18:00 opening reminder contains no `@all`.
- Both reminders contain `https://t.me/<bot_username>` and `/standup` instructions.
- Existing schedule times, topic routing, FSM, database schema, questions, and unrelated messages remain unchanged.
- Preserve all current uncommitted user changes, especially topic routing via `message_thread_id`.

---

## File Structure

- Create `tests/test_report_messages.py`: focused behavioral tests for published report formatting and reminder copy.
- Modify `bot/utils.py`: format the date and prominent clickable report author.
- Modify `bot/handlers/standup.py`: provide the report formatter with `user_id` and stored report date.
- Modify `bot/scheduler.py`: build the bot link from `bot.get_me()` and add the new reminder instructions.

### Task 1: Published report date and author block

**Files:**
- Create: `tests/test_report_messages.py`
- Modify: `bot/utils.py`
- Modify: `bot/handlers/standup.py`

**Interfaces:**
- Consumes: `report_date` as an ISO string (`YYYY-MM-DD`) already stored in FSM data, plus `callback.from_user.id` and `callback.from_user.full_name`.
- Produces: `group_report_text(user_id: int, full_name: str, report_date: str, today_text: str, tomorrow_text: str, time_str: str) -> str`.

- [ ] **Step 1: Write the failing formatter test**

```python
import unittest

from bot.utils import group_report_text


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
```

- [ ] **Step 2: Run the formatter test and verify RED**

Run: `python -m unittest tests.test_report_messages.GroupReportTextTests -v`

Expected: FAIL because the current `group_report_text` signature does not accept `user_id` or `report_date`.

- [ ] **Step 3: Implement the minimal report formatter**

In `bot/utils.py`, import `escape` and replace the group formatter with:

```python
from html import escape


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
```

In `bot/handlers/standup.py`, update only the call:

```python
group_text = group_report_text(
    callback.from_user.id,
    callback.from_user.full_name,
    report_date,
    data["today_text"],
    data["tomorrow_text"],
    now.strftime("%H:%M"),
)
```

- [ ] **Step 4: Run the formatter and existing topic tests and verify GREEN**

Run: `python -m unittest tests.test_report_messages.GroupReportTextTests tests.test_topic_binding.TopicDestinationTests.test_submitted_report_is_published_in_selected_topic -v`

Expected: both tests PASS, and the existing `message_thread_id` argument remains present.

- [ ] **Step 5: Commit the report formatting change**

```powershell
git add -- bot/utils.py bot/handlers/standup.py tests/test_report_messages.py
git commit -m "feat: show report date and author"
```

### Task 2: Bot link and instructions in both reminders

**Files:**
- Modify: `tests/test_report_messages.py`
- Modify: `bot/scheduler.py`

**Interfaces:**
- Consumes: `await bot.get_me()` returning the running bot's Telegram user with a non-empty `username`.
- Produces: opening and pre-close messages containing `https://t.me/<username>` and the `/standup` instruction while retaining topic routing and pending-member mentions.

- [ ] **Step 1: Write failing reminder tests**

Append to `tests/test_report_messages.py`:

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.scheduler import job_open_reminder, job_pre_close_reminder


GROUP_ID = -100123
THREAD_ID = 41


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
        self.assertIn("@employee", message)
        self.assertIn("https://t.me/daily_report_bot", message)
        self.assertIn("Запустите бота", message)
        self.assertIn("/standup", message)
        self.assertEqual(
            self.bot.send_message.await_args.kwargs["message_thread_id"], THREAD_ID
        )
```

- [ ] **Step 2: Run the reminder tests and verify RED**

Run: `python -m unittest tests.test_report_messages.ReminderTextTests -v`

Expected: FAIL because the opening reminder still includes `@all` and neither message includes the bot link or full instructions.

- [ ] **Step 3: Implement a focused bot-link helper and update both message bodies**

In `bot/scheduler.py`, add:

```python
async def _bot_link(bot: Bot) -> str:
    bot_user = await bot.get_me()
    return f"https://t.me/{bot_user.username}"
```

In each reminder job, resolve `bot_link = await _bot_link(bot)` only after all early-return conditions. Replace the opening message body with:

```python
(
    "🔔 Напоминание!\n\n"
    "Приём ежедневных отчётов открыт.\n"
    f"Пожалуйста, отправьте отчёт до {group['window_end']}.\n\n"
    f"🤖 Напишите отчёт боту: {bot_link}\n"
    "Запустите бота и начните заполнение командой /standup"
)
```

Keep the pending mentions and timing text in the pre-close message, then end it with:

```python
(
    f"🤖 Напишите отчёт боту: {bot_link}\n"
    "Запустите бота и начните заполнение командой /standup"
)
```

Do not change `message_thread_id`, schedule triggers, or summary messages.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m unittest tests.test_report_messages -v`

Expected: all report-message tests PASS.

- [ ] **Step 5: Run the complete regression suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS with no errors or failures.

- [ ] **Step 6: Review the exact diff for scope**

Run: `git diff -- bot/utils.py bot/handlers/standup.py bot/scheduler.py tests/test_report_messages.py`

Expected: only the approved report formatting, reminder copy, bot-link lookup, and tests are present; the pre-existing topic-routing lines remain unchanged.

- [ ] **Step 7: Commit the reminder change**

```powershell
git add -- bot/scheduler.py tests/test_report_messages.py
git commit -m "feat: improve report reminders"
```
