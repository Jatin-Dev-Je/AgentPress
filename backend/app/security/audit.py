from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AuthFailureEvent:
    ts_ms: int
    method: str
    path: str
    client_ip: str | None
    reason: str


class InMemoryAuditLog:
    def __init__(self, *, max_events: int) -> None:
        self._max = max(1, int(max_events))
        self._events: list[Any] = []

    def append(self, event: Any) -> None:
        self._events.append(event)
        if len(self._events) > self._max:
            # Drop oldest.
            extra = len(self._events) - self._max
            del self._events[0:extra]

    def list(self, *, limit: int = 200) -> list[dict]:
        limit = max(1, int(limit))
        out = self._events[-limit:]
        return [asdict(e) if hasattr(e, "__dataclass_fields__") else dict(e) for e in out]


def now_ms() -> int:
    return int(time.time() * 1000)
