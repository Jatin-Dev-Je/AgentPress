from __future__ import annotations

import json
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _write(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _ok(req_id: str, result: dict) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "result": result})


def _err(req_id: str, code: int, message: str, data: dict | None = None) -> None:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    _write({"jsonrpc": "2.0", "id": req_id, "error": err})


@dataclass(frozen=True)
class PluginConfig:
    base_dir: Path
    max_bytes: int
    allowed_extensions: list[str]
    deny_patterns: list[str]


def _load_config(context: dict) -> PluginConfig:
    cfg = context.get("plugin_config") or {}
    if not isinstance(cfg, dict):
        cfg = {}

    base_dir_raw = cfg.get("base_dir")
    if not isinstance(base_dir_raw, str) or not base_dir_raw.strip():
        raise ValueError("plugin_config.base_dir is required")

    base_dir = Path(base_dir_raw).expanduser()
    if not base_dir.is_absolute():
        base_dir = (Path.cwd() / base_dir).resolve()
    else:
        base_dir = base_dir.resolve()

    max_bytes = cfg.get("max_bytes", 200000)
    try:
        max_bytes = int(max_bytes)
    except Exception:
        max_bytes = 200000
    max_bytes = max(1024, min(2_000_000, max_bytes))

    allowed_ext = cfg.get("allowed_extensions")
    if allowed_ext is None:
        allowed_extensions = []
    elif isinstance(allowed_ext, list):
        allowed_extensions = [str(x) for x in allowed_ext if str(x)]
    else:
        allowed_extensions = []

    deny = cfg.get("deny_patterns")
    if isinstance(deny, list):
        deny_patterns = [str(x) for x in deny if str(x)]
    else:
        deny_patterns = ["..", "~"]

    return PluginConfig(
        base_dir=base_dir,
        max_bytes=max_bytes,
        allowed_extensions=allowed_extensions,
        deny_patterns=deny_patterns,
    )


def _resolve_path(*, cfg: PluginConfig, rel_path: str) -> Path:
    p = (rel_path or "").strip()
    if not p:
        raise ValueError("path is required")

    for pat in cfg.deny_patterns:
        if pat and pat in p:
            raise ValueError("path contains a denied pattern")

    candidate = (cfg.base_dir / p).resolve()
    try:
        if not candidate.is_relative_to(cfg.base_dir):
            raise ValueError("path escapes base_dir")
    except AttributeError:
        # Compatibility fallback (should not be needed on Py3.11)
        if not str(candidate).startswith(str(cfg.base_dir)):
            raise ValueError("path escapes base_dir")

    return candidate


def _check_extension(*, cfg: PluginConfig, path: Path) -> None:
    if not cfg.allowed_extensions:
        return
    ext = path.suffix.lower()
    allowed = {e.lower() for e in cfg.allowed_extensions}
    if ext not in allowed:
        raise ValueError(f"extension '{ext}' is not allowed")


def _tools_list() -> dict:
    return {
        "tools": [
            {
                "name": "list_dir",
                "description": "List files under the configured base_dir (optionally under a relative subpath).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path within base_dir", "default": ""},
                        "recursive": {"type": "boolean", "default": False},
                        "limit": {"type": "integer", "default": 200, "minimum": 1, "maximum": 2000}
                    },
                    "required": []
                },
            },
            {
                "name": "read_file",
                "description": "Read a text file within base_dir (truncated to max_bytes).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path within base_dir"},
                        "max_bytes": {"type": "integer", "description": "Override max bytes for this read", "minimum": 256, "maximum": 2000000}
                    },
                    "required": ["path"]
                },
            },
            {
                "name": "summarize_file",
                "description": "Return file content plus metadata suitable for LLM summarization (the LLM produces the summary).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "max_chars": {"type": "integer", "default": 12000, "minimum": 200, "maximum": 200000}
                    },
                    "required": ["path"]
                },
            },
        ]
    }


def _list_dir(*, cfg: PluginConfig, rel_path: str, recursive: bool, limit: int) -> dict:
    root = cfg.base_dir if not rel_path.strip() else _resolve_path(cfg=cfg, rel_path=rel_path)
    if not root.exists():
        raise ValueError("path not found")
    if not root.is_dir():
        raise ValueError("path is not a directory")

    limit = max(1, min(2000, int(limit)))

    items: list[dict[str, Any]] = []
    if recursive:
        iterator = root.rglob("*")
    else:
        iterator = root.glob("*")

    for p in iterator:
        if len(items) >= limit:
            break
        try:
            rel = str(p.relative_to(cfg.base_dir)).replace("\\", "/")
        except Exception:
            continue

        kind = "dir" if p.is_dir() else "file"
        size = None
        if kind == "file":
            try:
                size = p.stat().st_size
            except Exception:
                size = None

        items.append({"path": rel, "type": kind, "size": size})

    return {"base_dir": str(cfg.base_dir), "items": items, "truncated": len(items) >= limit}


def _read_file(*, cfg: PluginConfig, rel_path: str, max_bytes_override: int | None) -> dict:
    path = _resolve_path(cfg=cfg, rel_path=rel_path)
    if not path.exists() or not path.is_file():
        raise ValueError("file not found")

    _check_extension(cfg=cfg, path=path)

    max_bytes = cfg.max_bytes
    if max_bytes_override is not None:
        try:
            max_bytes = int(max_bytes_override)
        except Exception:
            max_bytes = cfg.max_bytes
        max_bytes = max(256, min(2_000_000, max_bytes))

    data = path.read_bytes()[:max_bytes]
    text = data.decode("utf-8", errors="replace")

    return {
        "path": str(path.relative_to(cfg.base_dir)).replace("\\", "/"),
        "bytes_read": len(data),
        "truncated": path.stat().st_size > len(data),
        "content": [{"type": "text", "text": text}],
    }


def _summarize_file(*, cfg: PluginConfig, rel_path: str, max_chars: int) -> dict:
    out = _read_file(cfg=cfg, rel_path=rel_path, max_bytes_override=None)
    text = ""
    try:
        content = out.get("content") or []
        if isinstance(content, list) and content and isinstance(content[0], dict):
            text = str(content[0].get("text") or "")
    except Exception:
        text = ""

    max_chars = max(200, min(200_000, int(max_chars)))
    excerpt = text[:max_chars]

    return {
        "path": out.get("path"),
        "bytes_read": out.get("bytes_read"),
        "truncated": out.get("truncated"),
        "excerpt": excerpt,
        "prompt": "Summarize the following file excerpt. Include key points, action items, and any warnings.\n\n" + excerpt,
    }


def _tools_call(params: dict) -> dict:
    name = params.get("name")
    args = params.get("arguments") or {}
    context = params.get("context") or {}

    cfg = _load_config(context)

    if name == "list_dir":
        rel_path = str(args.get("path") or "")
        recursive = bool(args.get("recursive") or False)
        limit = args.get("limit", 200)
        return _list_dir(cfg=cfg, rel_path=rel_path, recursive=recursive, limit=limit)

    if name == "read_file":
        rel_path = args.get("path")
        if not isinstance(rel_path, str):
            raise ValueError("'path' must be a string")
        max_bytes_override = args.get("max_bytes")
        if max_bytes_override is not None and not isinstance(max_bytes_override, (int, float, str)):
            raise ValueError("'max_bytes' must be a number")
        return _read_file(cfg=cfg, rel_path=rel_path, max_bytes_override=int(max_bytes_override) if max_bytes_override is not None else None)

    if name == "summarize_file":
        rel_path = args.get("path")
        if not isinstance(rel_path, str):
            raise ValueError("'path' must be a string")
        max_chars = args.get("max_chars", 12000)
        return _summarize_file(cfg=cfg, rel_path=rel_path, max_chars=int(max_chars))

    raise ValueError(f"Unknown tool: {name}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params") or {}

            if not req_id:
                continue

            if method == "initialize":
                _ok(req_id, {"server": {"name": "file-summarize", "version": "0.1.0"}})
            elif method == "tools/list":
                _ok(req_id, _tools_list())
            elif method == "tools/call":
                _ok(req_id, _tools_call(params))
            else:
                _err(req_id, -32601, f"Method not found: {method}")
        except Exception as e:
            req_id = None
            try:
                req_id = json.loads(line).get("id")
            except Exception:
                pass
            if req_id:
                _err(req_id, -32000, str(e), {"trace": traceback.format_exc()})


if __name__ == "__main__":
    main()
