import json
import sys
import time
import urllib.request
import urllib.error
from typing import Any

MAX_BYTES = 500_000
TIMEOUT = 8


def write(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def ok(req_id: str, result: dict) -> None:
    write({"jsonrpc": "2.0", "id": req_id, "result": result})


def err(req_id: str, code: int, message: str) -> None:
    write({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def tools_list() -> dict:
    return {
        "tools": [
            {
                "name": "ping",
                "description": "GET a URL and report status, latency, and a small body excerpt.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "format": "uri"},
                        "headers": {"type": "object", "additionalProperties": True}
                    },
                    "required": ["url"],
                    "additionalProperties": False,
                },
            }
        ]
    }


def _read_config(context: dict[str, Any]) -> list[str]:
    cfg = context.get("plugin_config") or {}
    prefixes = cfg.get("allowed_prefixes")
    if prefixes is None:
        return []
    if not isinstance(prefixes, list):
        raise ValueError("allowed_prefixes must be an array")
    vals: list[str] = []
    for p in prefixes:
        if isinstance(p, str):
            vals.append(p.rstrip("/"))
    return vals


def _is_allowed(url: str, prefixes: list[str]) -> bool:
    if not prefixes:
        return url.startswith("http://") or url.startswith("https://")
    for p in prefixes:
        if url.startswith(p):
            return True
    return False


def _ping(url: str, headers: dict | None) -> dict:
    req_headers = {"User-Agent": "agentpress-health-ping"}
    if headers and isinstance(headers, dict):
        for k, v in headers.items():
            if isinstance(k, str) and isinstance(v, str):
                req_headers[k] = v

    req = urllib.request.Request(url=url, method="GET", headers=req_headers)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read(MAX_BYTES + 1)
            truncated = len(raw) > MAX_BYTES
            if truncated:
                raw = raw[:MAX_BYTES]
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            snippet = raw.decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
            return {
                "status": resp.status,
                "elapsed_ms": elapsed_ms,
                "truncated": truncated,
                "body_excerpt": snippet[:800],
                "url": url,
            }
    except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        detail = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
        raise RuntimeError(f"HTTP {e.code} after {elapsed_ms}ms: {detail[:400]}")
    except urllib.error.URLError as e:  # type: ignore[attr-defined]
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        raise RuntimeError(f"Request failed after {elapsed_ms}ms: {getattr(e, 'reason', str(e))}")


def tools_call(params: dict) -> dict:
    name = params.get("name")
    args = params.get("arguments") or {}
    context = params.get("context") or {}

    if name != "ping":
        raise ValueError(f"Unknown tool: {name}")

    url = args.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url is required")
    url = url.strip()

    allowed = _read_config(context)
    if not _is_allowed(url, allowed):
        raise ValueError("url not allowed by plugin configuration")

    headers = args.get("headers") if isinstance(args.get("headers"), dict) else None
    result = _ping(url, headers)
    return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        req = json.loads(line)
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}

        if not req_id:
            continue

        try:
            if method == "initialize":
                ok(req_id, {"server": {"name": "health-ping", "version": "0.1.0"}})
            elif method == "tools/list":
                ok(req_id, tools_list())
            elif method == "tools/call":
                ok(req_id, tools_call(params))
            else:
                err(req_id, -32601, f"Method not found: {method}")
        except Exception as e:
            err(req_id, -32000, str(e))


if __name__ == "__main__":
    main()
