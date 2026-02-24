import json
import sys
import urllib.parse
import urllib.request
import urllib.error
from typing import Any


MAX_BYTES = 2_000_000
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
                "name": "http_request",
                "description": "Perform an HTTP GET or POST against an allowlisted base URL.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "method": {"type": "string", "enum": ["GET", "POST"], "default": "GET"},
                        "base": {"type": "string", "description": "Optional override base URL if multiple are allowed."},
                        "path": {"type": "string", "description": "Path appended to the base URL, e.g. /repos"},
                        "query": {"type": "object", "description": "Query parameters", "additionalProperties": True},
                        "body": {"type": "object", "description": "JSON body for POST", "additionalProperties": True},
                        "headers": {"type": "object", "description": "Optional headers", "additionalProperties": True}
                    },
                    "required": ["path"],
                    "additionalProperties": False
                }
            }
        ]
    }


def _read_config(context: dict[str, Any]) -> dict:
    return context.get("plugin_config") or {}


def _pick_base(config: dict, args: dict) -> str:
    bases = config.get("allowed_bases") or []
    if not isinstance(bases, list) or not bases:
        raise ValueError("allowed_bases not configured")

    base_override = args.get("base")
    if base_override:
        if base_override not in bases:
            raise ValueError("base is not in allowlist")
        return base_override.rstrip("/")

    if len(bases) == 1:
        return str(bases[0]).rstrip("/")

    raise ValueError("multiple bases configured; provide base in arguments")


def _build_url(base: str, path: str, query: dict | None) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        raise ValueError("path must be relative, not an absolute URL")

    url = base.rstrip("/") + "/" + path.lstrip("/")
    if query:
        qs = urllib.parse.urlencode(query, doseq=True)
        url = url + ("?" + qs)
    if not url.startswith(base):
        raise ValueError("constructed URL is not under allowed base")
    return url


def _http_request(method: str, url: str, body: dict | None, headers: dict | None) -> dict:
    data_bytes = None
    req_headers = {"Accept": "application/json"}

    if headers and isinstance(headers, dict):
        for k, v in headers.items():
            if isinstance(k, str) and isinstance(v, str):
                req_headers[k] = v

    if body is not None:
        data_bytes = json.dumps(body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url=url, method=method, headers=req_headers, data=data_bytes)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read(MAX_BYTES + 1)
            truncated = len(raw) > MAX_BYTES
            if truncated:
                raw = raw[:MAX_BYTES]
            text = raw.decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
            parsed = None
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None
            return {
                "status": resp.status,
                "url": url,
                "headers": {"content-type": resp.headers.get("Content-Type"), "content-length": resp.headers.get("Content-Length")},
                "truncated": truncated,
                "json": parsed,
                "text": text if parsed is None else None,
            }
    except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
        detail = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
        raise RuntimeError(f"HTTP {e.code}: {detail[:400]}")
    except urllib.error.URLError as e:  # type: ignore[attr-defined]
        raise RuntimeError(f"Request failed: {getattr(e, 'reason', str(e))}")


def tools_call(params: dict) -> dict:
    name = params.get("name")
    args = params.get("arguments") or {}
    context = params.get("context") or {}

    if name != "http_request":
        raise ValueError(f"Unknown tool: {name}")

    config = _read_config(context)

    method = str(args.get("method") or "GET").upper()
    if method not in {"GET", "POST"}:
        raise ValueError("method must be GET or POST")

    path = args.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path is required")

    base = _pick_base(config, args)
    url = _build_url(base, path, args.get("query") if isinstance(args.get("query"), dict) else None)

    body = args.get("body") if method == "POST" else None
    if body is not None and not isinstance(body, dict):
        raise ValueError("body must be an object for POST")

    headers = args.get("headers") if isinstance(args.get("headers"), dict) else None

    result = _http_request(method=method, url=url, body=body, headers=headers)
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
                ok(req_id, {"server": {"name": "http-requester", "version": "0.1.0"}})
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
