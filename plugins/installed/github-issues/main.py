from __future__ import annotations

import json
import sys
import traceback
from dataclasses import dataclass
from typing import Any

import httpx


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
    token: str | None
    api_base: str
    default_repo: str | None
    user_agent: str
    max_items: int


def _load_config(context: dict) -> PluginConfig:
    cfg = context.get("plugin_config") or {}
    if not isinstance(cfg, dict):
        cfg = {}

    token = cfg.get("token")
    if not isinstance(token, str) or not token.strip():
        token = None

    api_base = cfg.get("api_base")
    if not isinstance(api_base, str) or not api_base.strip():
        api_base = "https://api.github.com"
    api_base = api_base.rstrip("/")

    default_repo = cfg.get("default_repo")
    if not isinstance(default_repo, str) or not default_repo.strip():
        default_repo = None

    user_agent = cfg.get("user_agent")
    if not isinstance(user_agent, str) or not user_agent.strip():
        user_agent = "agentpress-github-issues/0.1.0"

    max_items = cfg.get("max_items", 50)
    try:
        max_items = int(max_items)
    except Exception:
        max_items = 50
    max_items = max(1, min(200, max_items))

    return PluginConfig(
        token=token,
        api_base=api_base,
        default_repo=default_repo,
        user_agent=user_agent,
        max_items=max_items,
    )


def _headers(cfg: PluginConfig) -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": cfg.user_agent,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if cfg.token:
        h["Authorization"] = f"Bearer {cfg.token}"
    return h


def _require_repo(cfg: PluginConfig, repo: Any) -> str:
    if isinstance(repo, str) and repo.strip():
        r = repo.strip()
    elif cfg.default_repo:
        r = cfg.default_repo
    else:
        raise ValueError("repo is required (owner/repo) or set plugin_config.default_repo")

    if "/" not in r:
        raise ValueError("repo must be in the form owner/repo")
    return r


def _tools_list() -> dict:
    return {
        "tools": [
            {
                "name": "list_issues",
                "description": "List issues for a repository.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string", "description": "owner/repo"},
                        "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
                        "labels": {"type": "string", "description": "Comma-separated labels"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 30},
                    },
                    "required": []
                },
            },
            {
                "name": "get_issue",
                "description": "Fetch a single issue by number.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string", "description": "owner/repo"},
                        "number": {"type": "integer"},
                    },
                    "required": ["number"]
                },
            },
        ]
    }


def _list_issues(cfg: PluginConfig, args: dict) -> dict:
    repo = _require_repo(cfg, args.get("repo"))
    owner, name = repo.split("/", 1)

    state = args.get("state", "open")
    if state not in ("open", "closed", "all"):
        state = "open"

    labels = args.get("labels")
    if labels is not None and not isinstance(labels, str):
        labels = None

    limit = args.get("limit", 30)
    try:
        limit = int(limit)
    except Exception:
        limit = 30
    limit = max(1, min(cfg.max_items, limit))

    url = f"{cfg.api_base}/repos/{owner}/{name}/issues"
    params: dict[str, Any] = {
        "state": state,
        "per_page": min(100, limit),
    }
    if labels:
        params["labels"] = labels

    with httpx.Client(timeout=20.0) as client:
        r = client.get(url, headers=_headers(cfg), params=params)

    if r.status_code >= 400:
        raise RuntimeError(f"GitHub API error {r.status_code}: {r.text}")

    data = r.json()
    if not isinstance(data, list):
        raise RuntimeError("Unexpected GitHub response")

    items: list[dict[str, Any]] = []
    for it in data:
        if len(items) >= limit:
            break
        if not isinstance(it, dict):
            continue
        # GitHub returns PRs in this endpoint; skip them.
        if "pull_request" in it:
            continue

        labels_out: list[str] = []
        labels_raw = it.get("labels")
        if isinstance(labels_raw, list):
            for l in labels_raw:
                if isinstance(l, dict) and isinstance(l.get("name"), str):
                    labels_out.append(l["name"])

        body = it.get("body")
        if not isinstance(body, str):
            body = ""
        body_excerpt = body[:1200]

        items.append(
            {
                "number": it.get("number"),
                "title": it.get("title"),
                "state": it.get("state"),
                "url": it.get("html_url"),
                "labels": labels_out,
                "created_at": it.get("created_at"),
                "updated_at": it.get("updated_at"),
                "body_excerpt": body_excerpt,
            }
        )

    return {"repo": repo, "count": len(items), "items": items}


def _get_issue(cfg: PluginConfig, args: dict) -> dict:
    repo = _require_repo(cfg, args.get("repo"))
    owner, name = repo.split("/", 1)

    number = args.get("number")
    if not isinstance(number, int):
        try:
            number = int(number)
        except Exception:
            raise ValueError("number must be an integer")

    url = f"{cfg.api_base}/repos/{owner}/{name}/issues/{number}"
    with httpx.Client(timeout=20.0) as client:
        r = client.get(url, headers=_headers(cfg))

    if r.status_code >= 400:
        raise RuntimeError(f"GitHub API error {r.status_code}: {r.text}")

    it = r.json()
    if not isinstance(it, dict):
        raise RuntimeError("Unexpected GitHub response")

    labels_out: list[str] = []
    labels_raw = it.get("labels")
    if isinstance(labels_raw, list):
        for l in labels_raw:
            if isinstance(l, dict) and isinstance(l.get("name"), str):
                labels_out.append(l["name"])

    body = it.get("body")
    if not isinstance(body, str):
        body = ""

    return {
        "repo": repo,
        "number": it.get("number"),
        "title": it.get("title"),
        "state": it.get("state"),
        "url": it.get("html_url"),
        "labels": labels_out,
        "created_at": it.get("created_at"),
        "updated_at": it.get("updated_at"),
        "body": body[:20000],
    }


def _tools_call(params: dict) -> dict:
    name = params.get("name")
    args = params.get("arguments") or {}
    context = params.get("context") or {}

    cfg = _load_config(context)

    if name == "list_issues":
        return _list_issues(cfg, args)
    if name == "get_issue":
        return _get_issue(cfg, args)

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
                _ok(req_id, {"server": {"name": "github-issues", "version": "0.1.0"}})
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
