import json
import sys


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
                "name": "your_tool",
                "description": "Describe your tool.",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            }
        ]
    }


def tools_call(params: dict) -> dict:
    name = params.get("name")
    args = params.get("arguments") or {}
    context = params.get("context") or {}

    if name != "your_tool":
        raise ValueError(f"Unknown tool: {name}")

    # Use context["agent_id"] to scope anything sensitive.
    _ = context.get("agent_id")

    return {"content": [{"type": "text", "text": "ok"}]}


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

        if method == "initialize":
            ok(req_id, {"server": {"name": "your-plugin-id", "version": "0.1.0"}})
        elif method == "tools/list":
            ok(req_id, tools_list())
        elif method == "tools/call":
            ok(req_id, tools_call(params))
        else:
            err(req_id, -32601, f"Method not found: {method}")


if __name__ == "__main__":
    main()
