# database.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter


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
