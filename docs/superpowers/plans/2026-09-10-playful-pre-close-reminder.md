# Playful Pre-Close Reminder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the 20:00 reminder start with the bold playful line `😂 Ээээ, кетир отчёт!`.

**Architecture:** Change only the existing pre-close reminder text in `job_pre_close_reminder`. Extend its current behavioral test first, leaving scheduling, recipient selection, links, commands, and other messages untouched.

**Tech Stack:** Python 3.12, aiogram 3.15, `unittest`/`unittest.mock`.

## Global Constraints

- The exact first line is `😂 <b>Ээээ, кетир отчёт!</b>`.
- Only the 20:00 pre-close reminder changes.
- Existing mentions, bot link, `/standup`, topic routing, schedule, and all other bot behavior remain unchanged.

---

### Task 1: Add the playful first line

**Files:**
- Modify: `tests/test_report_messages.py`
- Modify: `bot/scheduler.py`

**Interfaces:**
- Consumes: the existing `job_pre_close_reminder(bot, db, group_id)` message flow.
- Produces: the same reminder payload, prefixed by `😂 <b>Ээээ, кетир отчёт!</b>\n\n`.

- [ ] **Step 1: Write the failing assertion**

Add this assertion immediately after reading `message` in `test_pre_close_reminder_keeps_mentions_and_explains_bot_flow`:

```python
self.assertTrue(message.startswith("😂 <b>Ээээ, кетир отчёт!</b>\n\n"))
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m unittest tests.test_report_messages.ReminderTextTests.test_pre_close_reminder_keeps_mentions_and_explains_bot_flow -v`

Expected: FAIL because the message currently starts with `🔔 Напоминание!`.

- [ ] **Step 3: Add the exact first line**

In `bot/scheduler.py`, change only the beginning of the `job_pre_close_reminder` message:

```python
"😂 <b>Ээээ, кетир отчёт!</b>\n\n"
"🔔 Напоминание!\n"
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `python -m unittest tests.test_report_messages.ReminderTextTests.test_pre_close_reminder_keeps_mentions_and_explains_bot_flow -v`

Expected: PASS.

- [ ] **Step 5: Run the full regression suite**

Run: `python -m unittest discover -s tests -v`

Expected: all 9 tests PASS with no failures or errors.

- [ ] **Step 6: Review scope**

Run: `git diff --check -- bot/scheduler.py tests/test_report_messages.py`

Expected: no whitespace errors; the new change consists only of one test assertion and one message prefix.

- [ ] **Step 7: Preserve the dirty working tree without an implementation commit**

Do not create an implementation commit because `bot/scheduler.py` and `tests/test_report_messages.py` contain existing uncommitted work from the immediately preceding approved task. Report the changed lines and verification result to the user.
