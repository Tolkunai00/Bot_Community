# Full Runtime Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Telegram report bot run continuously with the original 18:00 / 20:00 / 21:00 schedule in Asia/Almaty and fail safely when external services are temporarily unavailable.

**Architecture:** Keep SQLite, aiogram polling, and APScheduler. Make configuration deterministic, keep all schedule decisions in APScheduler, add explicit scheduler/runtime error handling, and protect Telegram message-size and state transitions with regression tests.

**Tech Stack:** Python 3.12, aiogram 3.31.0, aiosqlite 0.20.0, APScheduler 3.11.3, unittest.

## Global Constraints

- Preserve the existing database and connected groups.
- Use Asia/Almaty for connected groups.
- Schedule opening at 18:00, pending reminder at 20:00, and summary at 21:00.
- Keep exactly one background polling process.
- Never expose the bot token in test or log output.

---

### Task 1: Deterministic configuration and schedule

**Files:**
- Modify: `.env`
- Modify: `.env.example`
- Modify: `bot/config.py`
- Modify: `bot/scheduler.py`
- Test: `tests/test_config.py`
- Test: `tests/test_report_messages.py`

**Interfaces:**
- Consumes: `Config`, `schedule_group_jobs`, SQLite group rows.
- Produces: validated `Config.reminder_time == "20:00"` and explicit UTC scheduler base timezone with per-group cron timezones.

- [ ] Add failing tests for exact `HH:MM` validation, project-root-relative database paths, scheduler timezone, and 18:00 / 20:00 / 21:00 triggers.
- [ ] Run the focused tests and confirm the expected failures.
- [ ] Resolve `.env` from the project root, validate timezone/time fields, restore `REMINDER_TIME=20:00`, and configure APScheduler without relying on the Windows system timezone.
- [ ] Run the focused tests and confirm they pass.

### Task 2: Handler and message reliability

**Files:**
- Modify: `bot/handlers/standup.py`
- Modify: `bot/scheduler.py`
- Modify: `bot/utils.py`
- Test: `tests/test_report_messages.py`
- Test: `tests/test_topic_binding.py`

**Interfaces:**
- Consumes: Telegram messages/callbacks and generated HTML.
- Produces: bounded valid Telegram HTML, retryable report publication, and scheduler jobs that do not terminate on transient Telegram failures.

- [ ] Add failing tests for the closing boundary, oversized reports, missing callback state, and scheduled-send network failure.
- [ ] Run the focused tests and confirm the expected failures.
- [ ] Add input limits, safe callback validation, and isolated scheduler error handling while preserving successful paths.
- [ ] Run the focused tests and confirm they pass.

### Task 3: Database and process lifecycle

**Files:**
- Modify: `bot/database.py`
- Modify: `bot/main.py`
- Test: `tests/test_main.py`
- Test: `tests/test_topic_binding.py`

**Interfaces:**
- Consumes: database path and Telegram connectivity.
- Produces: clean database startup/close behavior, schema repair, and continuous polling reconnect behavior.

- [ ] Add failing tests for connection cleanup on initialization failure and idempotent close.
- [ ] Run the focused tests and confirm the expected failures.
- [ ] Implement cleanup and lifecycle guards without changing stored reports or memberships.
- [ ] Run the focused tests and confirm they pass.

### Task 4: Full verification and live startup

**Files:**
- Modify: `README.md`
- Inspect: `bot/daily_report_bot.db`
- Inspect: `bot.stderr.log`

**Interfaces:**
- Consumes: completed implementation and current production configuration.
- Produces: verified one-process bot runtime and documented launch/change procedure.

- [ ] Run all unit tests, dependency checks, import checks, SQLite integrity checks, and diff whitespace checks.
- [ ] Verify cron triggers for every connected group are 18:00 / 20:00 / 21:00 in Asia/Almaty.
- [ ] Start one hidden bot process, confirm Telegram identity and polling in the log, and verify no second bot process exists.
- [ ] Update README with the verified schedule, launch command, log locations, and recovery guidance.
