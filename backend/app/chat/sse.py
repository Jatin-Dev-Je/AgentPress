from __future__ import annotations

import json


def sse(event: str, data: dict) -> bytes:
    payload = json.dumps(data, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")
