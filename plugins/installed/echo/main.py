import json
import sys
import traceback
import uuid


def _write(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _ok(req_id: str, result: dict) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "result": result})


def _err(req_id: str, code: int, message: str, data: dict | None = None) -> None:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    _write({"jsonrpc": "2.0", "id": req_id, "error": err})


def _tools_list() -> dict:
    return {
        "tools": [
            {
                "name": "echo",
                "description": "Echo back the provided text.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            }
        ]
    }


def _tools_call(params: dict) -> dict:
    name = params.get("name")
    args = params.get("arguments") or {}
    context = params.get("context") or {}

    if name != "echo":
        raise ValueError(f"Unknown tool: {name}")

    text = args.get("text")
    if not isinstance(text, str):
        raise ValueError("'text' must be a string")

    agent_id = context.get("agent_id")

    return {
        "content": [
            {
                "type": "text",
                "text": text,
            }
        ],
        "meta": {"agent_id": agent_id},
        "request_id": uuid.uuid4().hex,
    }


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
                _ok(req_id, {"server": {"name": "echo", "version": "0.1.0"}})
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
