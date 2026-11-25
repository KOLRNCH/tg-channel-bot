"""SQLite storage mapping subscribers to separate forum topics or DM reply IDs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite


@dataclass(frozen=True, slots=True)
class UserTopic:
    """Mapping between a Telegram subscriber and their dedicated forum topic."""

    user_id: int
    topic_thread_id: int
    username: str | None
    full_name: str
    is_banned: bool
    is_closed: bool


class Database:
    """Async SQLite repository for feedback topics and fallback PM message links."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open SQLite connection and ensure required tables exist."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_topics (
                user_id INTEGER PRIMARY KEY,
                topic_thread_id INTEGER NOT NULL UNIQUE,
                username TEXT,
                full_name TEXT NOT NULL,
                is_banned INTEGER NOT NULL DEFAULT 0,
                is_closed INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dm_links (
                admin_message_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                banned_at TEXT NOT NULL
            );
            """
        )
        await self._conn.commit()

    async def close(self) -> None:
        """Close the active SQLite connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        """Return active SQLite connection or raise if uninitialized."""
        if self._conn is None:
            raise RuntimeError("Database is not connected")
        return self._conn

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _row_to_topic(row: aiosqlite.Row) -> UserTopic:
        return UserTopic(
            user_id=int(row["user_id"]),
            topic_thread_id=int(row["topic_thread_id"]),
            username=row["username"],
            full_name=str(row["full_name"]),
            is_banned=bool(row["is_banned"]),
            is_closed=bool(row["is_closed"]),
        )

    async def get_topic_by_user(self, user_id: int) -> UserTopic | None:
        """Look up the forum topic assigned to `user_id`."""
        async with self.conn.execute(
            "SELECT * FROM user_topics WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return self._row_to_topic(row) if row else None

    async def get_topic_by_thread(self, topic_thread_id: int) -> UserTopic | None:
        """Look up the subscriber assigned to a specific `topic_thread_id`."""
        async with self.conn.execute(
            "SELECT * FROM user_topics WHERE topic_thread_id = ?",
            (topic_thread_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return self._row_to_topic(row) if row else None

    async def upsert_topic(
        self,
        user_id: int,
        topic_thread_id: int,
        username: str | None,
        full_name: str,
    ) -> UserTopic:
        """Insert or update the subscriber-to-topic mapping."""
        now = self._now_iso()
        await self.conn.execute(
            """
            INSERT INTO user_topics (user_id, topic_thread_id, username, full_name, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                topic_thread_id = excluded.topic_thread_id,
                username = excluded.username,
                full_name = excluded.full_name,
                updated_at = excluded.updated_at
            """,
            (user_id, topic_thread_id, username, full_name, now),
        )
        await self.conn.commit()
        topic = await self.get_topic_by_user(user_id)
        assert topic is not None
        return topic

    async def set_topic_closed(self, user_id: int, is_closed: bool) -> None:
        """Mark a user's topic closed or open."""
        await self.conn.execute(
            "UPDATE user_topics SET is_closed = ?, updated_at = ? WHERE user_id = ?",
            (int(is_closed), self._now_iso(), user_id),
        )
        await self.conn.commit()

    async def is_user_banned(self, user_id: int) -> bool:
        """Return True if the user is blocked from using the feedback box."""
        async with self.conn.execute(
            "SELECT 1 FROM banned_users WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            return (await cursor.fetchone()) is not None

    async def set_user_banned(self, user_id: int, banned: bool) -> None:
        """Block or unblock `user_id` across both topic and PM fallback modes."""
        if banned:
            await self.conn.execute(
                "INSERT OR IGNORE INTO banned_users (user_id, banned_at) VALUES (?, ?)",
                (user_id, self._now_iso()),
            )
        else:
            await self.conn.execute(
                "DELETE FROM banned_users WHERE user_id = ?",
                (user_id,),
            )
        await self.conn.execute(
            "UPDATE user_topics SET is_banned = ?, updated_at = ? WHERE user_id = ?",
            (int(banned), self._now_iso(), user_id),
        )
        await self.conn.commit()

    async def save_dm_link(self, admin_message_id: int, user_id: int) -> None:
        """Associate an admin PM forwarded message ID with a subscriber ID."""
        await self.conn.execute(
            "INSERT OR REPLACE INTO dm_links (admin_message_id, user_id) VALUES (?, ?)",
            (admin_message_id, user_id),
        )
        await self.conn.commit()

    async def get_user_by_dm(self, admin_message_id: int) -> int | None:
        """Resolve subscriber `user_id` when admin replies in fallback PM mode."""
        async with self.conn.execute(
            "SELECT user_id FROM dm_links WHERE admin_message_id = ?",
            (admin_message_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return int(row["user_id"]) if row else None
