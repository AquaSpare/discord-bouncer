# database.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import aiosqlite
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


@dataclass
class SQLiteHistoryDB:
    """
    SQLite-backed DB with:
      - messages: append-only rows (each row = result.new_messages_json())
      - blacklist: user_id -> bool

    Async API matches InMemoryHistoryDB so you can swap back and forth.
    """

    con: aiosqlite.Connection

    # --- lifecycle -----------------------------------------------------------
    @classmethod
    async def open(cls, path: str | Path = "history.sqlite3") -> "SQLiteHistoryDB":
        con = await aiosqlite.connect(str(path))
        await con.executescript(_SCHEMA)  # run pragmas + table/index creation
        await con.commit()
        return cls(con)

    async def close(self) -> None:
        await self.con.close()

    # --- messages ------------------------------------------------------------
    async def add_messages(self, user_id: str, messages_json_bytes: bytes) -> None:
        await self.con.execute(
            "INSERT INTO messages (user_id, message_list) VALUES (?, ?)",
            (user_id, messages_json_bytes),
        )
        await self.con.commit()

    async def get_messages(self, user_id: str) -> List[ModelMessage]:
        async with self.con.execute(
            "SELECT message_list FROM messages WHERE user_id = ? ORDER BY id",
            (user_id,),
        ) as cur:
            rows = await cur.fetchall()

        messages: List[ModelMessage] = []
        for (blob,) in rows:
            messages.extend(ModelMessagesTypeAdapter.validate_json(blob))
        return messages

    async def delete_history(self, user_id: str) -> None:
        await self.con.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        await self.con.commit()

    # --- blacklist -----------------------------------------------------------
    async def is_blacklisted(self, user_id: str) -> bool:
        async with self.con.execute(
            "SELECT is_blacklisted FROM blacklist WHERE user_id = ?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        return bool(row[0]) if row is not None else False

    async def set_blacklisted(self, user_id: str, value: bool) -> None:
        # Upsert to ensure only one row per user_id
        await self.con.execute(
            """
            INSERT INTO blacklist (user_id, is_blacklisted)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET is_blacklisted=excluded.is_blacklisted
            """,
            (user_id, 1 if value else 0),
        )
        await self.con.commit()

    async def add_to_blacklist(self, user_id: str) -> None:
        await self.set_blacklisted(user_id, True)

    async def remove_from_blacklist(self, user_id: str) -> None:
        await self.set_blacklisted(user_id, False)


@dataclass
class InMemoryHistoryDB:
    """
    Minimal in-memory DB with:
      - append-only message rows per user (list of JSON blobs)
      - a blacklist table (user_id -> bool)

    Async API so you can swap to SQLite later without changing bot code.
    """

    _messages: Dict[str, List[bytes]] = field(default_factory=dict)
    _blacklist: Dict[str, bool] = field(default_factory=dict)

    # lifecycle ---------------------------------------------------------------

    @classmethod
    async def open(cls) -> "InMemoryHistoryDB":
        return cls()

    async def close(self) -> None:
        return

    # messages ----------------------------------------------------------------

    async def add_messages(self, user_id: str, messages_json_bytes: bytes) -> None:
        self._messages.setdefault(user_id, []).append(messages_json_bytes)

    async def get_messages(self, user_id: str) -> list[ModelMessage]:
        blobs = self._messages.get(user_id, [])
        messages: list[ModelMessage] = []
        for blob in blobs:
            messages.extend(ModelMessagesTypeAdapter.validate_json(blob))
        return messages

    async def delete_history(self, user_id: str) -> None:
        self._messages.pop(user_id, None)

    # blacklist ---------------------------------------------------------------

    async def is_blacklisted(self, user_id: str) -> bool:
        return self._blacklist.get(user_id, False)

    async def set_blacklisted(self, user_id: str, value: bool) -> None:
        if value:
            self._blacklist[user_id] = True
        else:
            # remove or set False; either is fine. We'll remove for cleanliness.
            self._blacklist.pop(user_id, None)

    # Convenience helpers

    async def add_to_blacklist(self, user_id: str) -> None:
        await self.set_blacklisted(user_id, True)

    async def remove_from_blacklist(self, user_id: str) -> None:
        await self.set_blacklisted(user_id, False)
