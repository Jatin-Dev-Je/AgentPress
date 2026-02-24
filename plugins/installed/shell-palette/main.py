import json
import shlex
import subprocess
import sys
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
                "name": "run_command",
                "description": "Run a whitelisted command by name (read-only palette).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Command name from the allowlist"}
                    },
                    "required": ["name"],
                    "additionalProperties": False,
                },
            }
        ]
    }


def _read_config(context: dict[str, Any]) -> tuple[dict[str, list[str]], int]:
    cfg = context.get("plugin_config") or {}
    commands = cfg.get("commands")
    if not isinstance(commands, list) or not commands:
        raise ValueError("commands allowlist not configured")
    mapping: dict[str, list[str]] = {}
    for item in commands:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        argv = item.get("argv")
        if isinstance(name, str) and isinstance(argv, list) and all(isinstance(s, str) for s in argv):
            mapping[name] = argv
    if not mapping:
        raise ValueError("commands allowlist empty")
    timeout = cfg.get("timeout_seconds") if isinstance(cfg.get("timeout_seconds"), int) else 5
    return mapping, max(1, int(timeout))


def _run(argv: list[str], timeout: int) -> dict:
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def tools_call(params: dict) -> dict:
    name = params.get("name")
    args = params.get("arguments") or {}
    context = params.get("context") or {}

    if name != "run_command":
        raise ValueError(f"Unknown tool: {name}")

    cmd_name = args.get("name")
    if not isinstance(cmd_name, str) or not cmd_name.strip():
        raise ValueError("name is required")

    mapping, timeout = _read_config(context)
    argv = mapping.get(cmd_name)
    if not argv:
        raise ValueError("command not allowed")

    result = _run(argv, timeout)
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
                ok(req_id, {"server": {"name": "shell-palette", "version": "0.1.0"}})
            elif method == "tools/list":
                ok(req_id, tools_list())
            elif method == "tools/call":
                ok(req_id, tools_call(params))
            else:
                err(req_id, -32601, f"Method not found: {method}")
        except subprocess.TimeoutExpired:
            err(req_id, -32000, "command timed out")
        except Exception as e:
            err(req_id, -32000, str(e))


if __name__ == "__main__":
    main()
