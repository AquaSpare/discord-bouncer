from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, TypeVar

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    message_list BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_userid_id
    ON messages (user_id, id);

CREATE TABLE IF NOT EXISTS blacklist (
    user_id TEXT PRIMARY KEY,
    is_blacklisted INTEGER NOT NULL CHECK (is_blacklisted IN (0,1))
);
"""

R = TypeVar("R")


@dataclass
class SQLiteHistoryDB:
    """
    Same async API as before, but implemented with the synchronous sqlite3 driver.
    Blocking DB work is offloaded via asyncio.to_thread, so your event loop stays snappy.
    """

    con: sqlite3.Connection

    # --- lifecycle -----------------------------------------------------------
    @classmethod
    async def open(cls, path: str | Path = "history.sqlite3") -> "SQLiteHistoryDB":
        # Create connection in a thread-safe way; allow cross-thread use
        def _connect() -> sqlite3.Connection:
            con = sqlite3.connect(str(path), check_same_thread=False)
            con.executescript(_SCHEMA)
            con.commit()
            return con

        con = await asyncio.to_thread(_connect)
        return cls(con)

    async def close(self) -> None:
        await self._to_thread(self.con.close)

    # --- messages ------------------------------------------------------------
    async def add_messages(self, user_id: str, messages_json_bytes: bytes) -> None:
        await self._execute(
            "INSERT INTO messages (user_id, message_list) VALUES (?, ?)",
            (user_id, messages_json_bytes),
            commit=True,
        )

    async def get_messages(self, user_id: str) -> List[ModelMessage]:
        cur = await self._execute(
            "SELECT message_list FROM messages WHERE user_id = ? ORDER BY id",
            (user_id,),
        )
        rows = await self._to_thread(cur.fetchall)
        messages: List[ModelMessage] = []
        for (blob,) in rows:
            messages.extend(ModelMessagesTypeAdapter.validate_json(blob))
        return messages

    async def delete_history(self, user_id: str) -> None:
        await self._execute(
            "DELETE FROM messages WHERE user_id = ?", (user_id,), commit=True
        )

    # --- blacklist -----------------------------------------------------------
    async def is_blacklisted(self, user_id: str) -> bool:
        cur = await self._execute(
            "SELECT is_blacklisted FROM blacklist WHERE user_id = ?",
            (user_id,),
        )
        row = await self._to_thread(cur.fetchone)
        return bool(row[0]) if row is not None else False

    async def set_blacklisted(self, user_id: str, value: bool) -> None:
        await self._execute(
            """
            INSERT INTO blacklist (user_id, is_blacklisted)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET is_blacklisted=excluded.is_blacklisted
            """,
            (user_id, 1 if value else 0),
            commit=True,
        )

    async def add_to_blacklist(self, user_id: str) -> None:
        await self.set_blacklisted(user_id, True)

    async def remove_from_blacklist(self, user_id: str) -> None:
        await self.set_blacklisted(user_id, False)

    # --- helpers -------------------------------------------------------------
    async def _execute(
        self, sql: str, params: tuple[Any, ...] = (), commit: bool = False
    ) -> sqlite3.Cursor:
        def _do() -> sqlite3.Cursor:
            cur = self.con.cursor()
            cur.execute(sql, params)
            if commit:
                self.con.commit()
            return cur

        return await self._to_thread(_do)

    async def _to_thread(self, fn: Callable[[], R]) -> R:
        return await asyncio.to_thread(fn)
