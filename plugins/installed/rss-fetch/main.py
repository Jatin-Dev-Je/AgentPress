import json
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from typing import Any

MAX_BYTES = 1_000_000
TIMEOUT = 10


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
                "name": "list_items",
                "description": "Fetch items from an RSS/Atom feed (title, link, published).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "feed_url": {"type": "string", "format": "uri"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10}
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            }
        ]
    }


def _read_config(context: dict[str, Any]) -> str | None:
    cfg = context.get("plugin_config") or {}
    url = cfg.get("feed_url")
    return url if isinstance(url, str) else None


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url=url, headers={"User-Agent": "agentpress-rss-fetch"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise RuntimeError("feed too large")
        return raw


def _parse(feed_bytes: bytes, limit: int) -> list[dict]:
    root = ET.fromstring(feed_bytes)
    items: list[dict] = []

    # RSS 2.0
    channel = root.find("channel")
    if channel is not None:
        for itm in channel.findall("item"):
            if len(items) >= limit:
                break
            title = (itm.findtext("title") or "").strip()
            link = (itm.findtext("link") or "").strip()
            published = (itm.findtext("pubDate") or "").strip()
            items.append({"title": title, "link": link, "published": published})
        return items

    # Atom
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall("atom:entry", ns):
        if len(items) >= limit:
            break
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        link_el = entry.find("atom:link", ns)
        link = ""
        if link_el is not None:
            link = link_el.get("href", "").strip()
        published = (entry.findtext("atom:updated", default="", namespaces=ns) or "").strip()
        items.append({"title": title, "link": link, "published": published})
    return items


def tools_call(params: dict) -> dict:
    name = params.get("name")
    args = params.get("arguments") or {}
    context = params.get("context") or {}

    if name != "list_items":
        raise ValueError(f"Unknown tool: {name}")

    feed_url = args.get("feed_url") if isinstance(args.get("feed_url"), str) else None
    if not feed_url:
        feed_url = _read_config(context)
    if not feed_url:
        raise ValueError("feed_url is required (argument or config)")

    limit = args.get("limit") if isinstance(args.get("limit"), int) else 10
    limit = max(1, min(limit, 50))

    try:
        raw = _fetch(feed_url)
        items = _parse(raw, limit)
    except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
        raise RuntimeError(f"HTTP {e.code}: {(e.reason if hasattr(e, 'reason') else str(e))}")
    except urllib.error.URLError as e:  # type: ignore[attr-defined]
        raise RuntimeError(f"Request failed: {getattr(e, 'reason', str(e))}")

    return {"content": [{"type": "text", "text": json.dumps(items, ensure_ascii=False)}]}


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
                ok(req_id, {"server": {"name": "rss-fetch", "version": "0.1.0"}})
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
