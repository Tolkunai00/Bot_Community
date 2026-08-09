import datetime
from typing import Optional
import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    group_id INTEGER PRIMARY KEY,
    title TEXT,
    connected INTEGER NOT NULL DEFAULT 1,
    window_start TEXT NOT NULL DEFAULT '18:00',
    window_end TEXT NOT NULL DEFAULT '21:00',
    timezone TEXT NOT NULL DEFAULT 'Asia/Bishkek'
);

CREATE TABLE IF NOT EXISTS members (
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT,
    full_name TEXT,
    PRIMARY KEY (group_id, user_id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    report_date TEXT NOT NULL,
    today_text TEXT,
    tomorrow_text TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    submitted_at TEXT,
    UNIQUE(group_id, user_id, report_date)
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()


    async def upsert_group(self, group_id: int, title: str, timezone: str):
        await self._conn.execute(
            """
            INSERT INTO groups (group_id, title, timezone)
            VALUES (?, ?, ?)
            ON CONFLICT(group_id) DO UPDATE SET
                title = excluded.title,
                connected = 1
            """,
            (group_id, title, timezone),
        )
        await self._conn.commit()

    async def set_group_connected(self, group_id: int, connected: bool):
        await self._conn.execute(
            "UPDATE groups SET connected = ? WHERE group_id = ?",
            (1 if connected else 0, group_id),
        )
        await self._conn.commit()

    async def get_group(self, group_id: int) -> Optional[aiosqlite.Row]:
        cursor = await self._conn.execute(
            "SELECT * FROM groups WHERE group_id = ?", (group_id,)
        )
        return await cursor.fetchone()

    async def get_connected_groups(self) -> list[aiosqlite.Row]:
        cursor = await self._conn.execute(
            "SELECT * FROM groups WHERE connected = 1"
        )
        return await cursor.fetchall()


    async def upsert_member(
        self, group_id: int, user_id: int, username: Optional[str], full_name: str
    ):
        await self._conn.execute(
            """
            INSERT INTO members (group_id, user_id, username, full_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(group_id, user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name
            """,
            (group_id, user_id, username, full_name),
        )
        await self._conn.commit()

    async def remove_member(self, group_id: int, user_id: int):
        await self._conn.execute(
            "DELETE FROM members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
        )
        await self._conn.commit()

    async def get_members(self, group_id: int) -> list[aiosqlite.Row]:
        cursor = await self._conn.execute(
            "SELECT * FROM members WHERE group_id = ?", (group_id,)
        )
        return await cursor.fetchall()

    async def get_member_count(self, group_id: int) -> int:
        cursor = await self._conn.execute(
            "SELECT COUNT(*) AS c FROM members WHERE group_id = ?", (group_id,)
        )
        row = await cursor.fetchone()
        return row["c"] if row else 0

    async def find_user_group(self, user_id: int) -> Optional[int]:
        cursor = await self._conn.execute(
            """
            SELECT m.group_id FROM members m
            JOIN groups g ON g.group_id = m.group_id
            WHERE m.user_id = ? AND g.connected = 1
            LIMIT 1
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["group_id"] if row else None


    async def get_today_report(
        self, group_id: int, user_id: int, report_date: str
    ) -> Optional[aiosqlite.Row]:
        cursor = await self._conn.execute(
            """
            SELECT * FROM reports
            WHERE group_id = ? AND user_id = ? AND report_date = ?
            """,
            (group_id, user_id, report_date),
        )
        return await cursor.fetchone()

    async def save_draft(
        self,
        group_id: int,
        user_id: int,
        report_date: str,
        today_text: str,
        tomorrow_text: str,
    ):
        await self._conn.execute(
            """
            INSERT INTO reports (group_id, user_id, report_date, today_text, tomorrow_text, status)
            VALUES (?, ?, ?, ?, ?, 'draft')
            ON CONFLICT(group_id, user_id, report_date) DO UPDATE SET
                today_text = excluded.today_text,
                tomorrow_text = excluded.tomorrow_text,
                status = 'draft'
            """,
            (group_id, user_id, report_date, today_text, tomorrow_text),
        )
        await self._conn.commit()

    async def submit_report(
        self, group_id: int, user_id: int, report_date: str, submitted_at: str
    ):
        await self._conn.execute(
            """
            UPDATE reports SET status = 'submitted', submitted_at = ?
            WHERE group_id = ? AND user_id = ? AND report_date = ?
            """,
            (submitted_at, group_id, user_id, report_date),
        )
        await self._conn.commit()

    async def get_submitted_user_ids(self, group_id: int, report_date: str) -> set[int]:
        cursor = await self._conn.execute(
            """
            SELECT user_id FROM reports
            WHERE group_id = ? AND report_date = ? AND status = 'submitted'
            """,
            (group_id, report_date),
        )
        rows = await cursor.fetchall()
        return {row["user_id"] for row in rows}


def today_str(tz) -> str:
    return datetime.datetime.now(tz).strftime("%Y-%m-%d")
