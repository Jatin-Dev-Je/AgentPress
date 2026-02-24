import json
import os
import sys
from pathlib import Path
from typing import Any


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
                "name": "list_dir",
                "description": "List files and directories relative to the sandbox root.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path", "default": "."}
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            },
            {
                "name": "read_file",
                "description": "Read a text file relative to the sandbox root (size-limited).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative file path"}
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        ]
    }


def _read_config(context: dict[str, Any]) -> tuple[Path, int]:
    cfg = context.get("plugin_config") or {}
    root = cfg.get("root_dir")
    if not isinstance(root, str) or not root.strip():
        raise ValueError("root_dir not configured")
    max_bytes = cfg.get("max_bytes") if isinstance(cfg.get("max_bytes"), int) else 200000
    return Path(root).resolve(), int(max_bytes)


def _resolve(root: Path, rel: str) -> Path:
    candidate = (root / rel).resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError("path escapes sandbox root")
    return candidate


def _list_dir(root: Path, rel: str) -> dict:
    target = _resolve(root, rel)
    if not target.exists() or not target.is_dir():
        raise ValueError("directory not found")
    items = []
    for entry in sorted(target.iterdir()):
        items.append(
            {
                "name": entry.name,
                "is_dir": entry.is_dir(),
                "size": entry.stat().st_size if entry.is_file() else None,
            }
        )
    return {"content": [{"type": "text", "text": json.dumps(items, ensure_ascii=False)}]}


def _read_file(root: Path, rel: str, max_bytes: int) -> dict:
    target = _resolve(root, rel)
    if not target.exists() or not target.is_file():
        raise ValueError("file not found")
    size = target.stat().st_size
    if size > max_bytes:
        raise ValueError(f"file too large (>{max_bytes} bytes)")
    data = target.read_bytes()
    text = data.decode("utf-8", errors="replace")
    return {
        "content": [
            {"type": "text", "text": text},
            {"type": "text", "text": f"\n\n(meta) bytes={size}"},
        ]
    }


def tools_call(params: dict) -> dict:
    name = params.get("name")
    args = params.get("arguments") or {}
    context = params.get("context") or {}

    root, max_bytes = _read_config(context)

    if name == "list_dir":
        rel = args.get("path") or "."
        if not isinstance(rel, str):
            raise ValueError("path must be a string")
        return _list_dir(root, rel)

    if name == "read_file":
        rel = args.get("path")
        if not isinstance(rel, str) or not rel.strip():
            raise ValueError("path is required")
        return _read_file(root, rel, max_bytes)

    raise ValueError(f"Unknown tool: {name}")


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
                ok(req_id, {"server": {"name": "fs-sandbox", "version": "0.1.0"}})
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
