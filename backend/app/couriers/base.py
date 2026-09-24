"""Shared helpers for courier clients."""
import time
from typing import Any, Hashable


class TTLCache:
    """Tiny in-memory cache so a demo does not hammer the courier testbed."""

    def __init__(self, ttl_seconds: float):
        self.ttl = ttl_seconds
        self._data: dict[Hashable, tuple[float, Any]] = {}

    def get(self, key: Hashable):
        hit = self._data.get(key)
        if hit is None:
            return None
        stored_at, value = hit
        if time.monotonic() - stored_at > self.ttl:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: Hashable, value: Any) -> None:
        self._data[key] = (time.monotonic(), value)

    def clear(self) -> None:
        self._data.clear()
