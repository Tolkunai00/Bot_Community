# Bishkek Timezone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make new and existing groups use `Asia/Bishkek` while keeping the 18:00 / 20:00 / 21:00 schedule.

**Architecture:** Change the configuration and schema defaults without removing support for other valid IANA timezones. Update the two persisted connected-group rows in one SQLite transaction, then verify configuration, cron triggers, and database integrity.

**Tech Stack:** Python 3.12, pytz, SQLite, APScheduler, unittest.

## Global Constraints

- Preserve all group, topic, member, and report data.
- Use `Asia/Bishkek` for both existing connected groups and as the default for new groups.
- Keep opening at 18:00, pending reminder at 20:00, and summary at 21:00.
- Do not expose or modify the bot token.

---

### Task 1: Change the default timezone with a regression test

**Files:**
- Modify: `tests/test_config.py`
- Modify: `bot/config.py`
- Modify: `bot/database.py`
- Modify: `.env`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: `load_config() -> Config` and the `groups.timezone` schema default.
- Produces: `Config.default_timezone == "Asia/Bishkek"` when the environment does not override it.

- [x] **Step 1: Write the failing default-timezone test**

```python
def test_default_timezone_is_bishkek(self):
    with patch.dict(os.environ, {"BOT_TOKEN": "123456:test-token"}, clear=True):
        config = load_config()

    self.assertEqual(config.default_timezone, "Asia/Bishkek")
```

- [x] **Step 2: Run the focused test and verify RED**

Run: `.venv\Scripts\python.exe -m unittest tests.test_config.ConfigTests.test_default_timezone_is_bishkek -v`

Expected: FAIL because the current code returns `Asia/Almaty`.

- [x] **Step 3: Apply the minimal default changes**

Change the fallback in `bot/config.py` and the SQL schema default in `bot/database.py` to `Asia/Bishkek`. Set `DEFAULT_TIMEZONE=Asia/Bishkek` in `.env` and `.env.example`. Replace `Asia/Almaty` with `Asia/Bishkek` in the README configuration example and keep `REMINDER_TIME=20:00`.

- [x] **Step 4: Run configuration tests and verify GREEN**

Run: `.venv\Scripts\python.exe -m unittest tests.test_config -v`

Expected: all configuration tests pass.

### Task 2: Update persisted groups and verify scheduling

**Files:**
- Modify: `bot/daily_report_bot.db`
- Modify: `tests/test_report_messages.py`

**Interfaces:**
- Consumes: connected rows in `groups` and `schedule_group_jobs(...)`.
- Produces: existing connected rows with `timezone == "Asia/Bishkek"` and cron triggers at 18:00 / 20:00 / 21:00 in that timezone.

- [x] **Step 1: Update the schedule fixture to Bishkek**

In `ScheduleTests.test_reminder_is_scheduled_for_configured_time`, use:

```python
"timezone": "Asia/Bishkek",
```

Add assertions that each trigger string includes `Asia/Bishkek` while retaining the existing hour/minute assertions.

- [x] **Step 2: Run the focused schedule test**

Run: `.venv\Scripts\python.exe -m unittest tests.test_report_messages.ScheduleTests -v`

Expected: PASS, confirming the scheduler accepts and preserves the Bishkek timezone.

- [x] **Step 3: Update existing connected groups transactionally**

Execute one SQLite transaction equivalent to:

```sql
UPDATE groups
SET timezone = 'Asia/Bishkek'
WHERE connected = 1;
```

Do not change any other columns or tables.

- [x] **Step 4: Verify the database**

Run a read-only check that prints `PRAGMA integrity_check`, all connected group IDs and timezones, and their unchanged window start/end values.

Expected: integrity is `ok`; both connected groups use `Asia/Bishkek`, `18:00`, and `21:00`.

- [x] **Step 5: Run full verification**

Run:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m pip check
git diff --check
```

Expected: all tests pass, dependencies are consistent, and the diff has no whitespace errors.
