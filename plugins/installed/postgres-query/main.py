from __future__ import annotations

import asyncio
import json
import re
import sys
import traceback
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg


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
    dsn: str
    max_rows: int
    timeout_seconds: float
    statement_timeout_ms: int


_POOL_BY_DSN: dict[str, asyncpg.Pool] = {}


def _load_config(context: dict) -> PluginConfig:
    cfg = context.get("plugin_config") or {}
    if not isinstance(cfg, dict):
        cfg = {}

    dsn = cfg.get("dsn")
    if not isinstance(dsn, str) or not dsn.strip():
        raise ValueError("plugin_config.dsn is required")
    dsn = dsn.strip()

    max_rows = cfg.get("max_rows", 200)
    try:
        max_rows = int(max_rows)
    except Exception:
        max_rows = 200
    max_rows = max(1, min(2000, max_rows))

    timeout_seconds = cfg.get("timeout_seconds", 10)
    try:
        timeout_seconds = float(timeout_seconds)
    except Exception:
        timeout_seconds = 10.0
    timeout_seconds = max(0.5, min(60.0, timeout_seconds))

    statement_timeout_ms = cfg.get("statement_timeout_ms", 10000)
    try:
        statement_timeout_ms = int(statement_timeout_ms)
    except Exception:
        statement_timeout_ms = 10000
    statement_timeout_ms = max(100, min(60000, statement_timeout_ms))

    return PluginConfig(
        dsn=dsn,
        max_rows=max_rows,
        timeout_seconds=timeout_seconds,
        statement_timeout_ms=statement_timeout_ms,
    )


def _to_jsonable(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (datetime, date, UUID, Decimal)):
        return str(v)
    if isinstance(v, bytes):
        return v.hex()
    if isinstance(v, list):
        return [_to_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _to_jsonable(val) for k, val in v.items()}
    return str(v)


_SQL_ALLOWED = re.compile(r"^\s*(with|select|show|explain)\b", re.IGNORECASE)


def _validate_sql(sql: str) -> None:
    s = (sql or "").strip()
    if not s:
        raise ValueError("sql is required")

    if not _SQL_ALLOWED.match(s):
        raise ValueError("Only read-only queries are allowed (WITH/SELECT/SHOW/EXPLAIN)")

    # Block multiple statements.
    if ";" in s:
        parts = [p for p in s.split(";") if p.strip()]
        if len(parts) > 1:
            raise ValueError("Multiple SQL statements are not allowed")


async def _get_pool(dsn: str) -> asyncpg.Pool:
    pool = _POOL_BY_DSN.get(dsn)
    if pool is not None:
        return pool

    # Keep this bounded.
    if len(_POOL_BY_DSN) >= 5:
        # Close an arbitrary pool.
        k, old = next(iter(_POOL_BY_DSN.items()))
        try:
            await old.close()
        except Exception:
            pass
        _POOL_BY_DSN.pop(k, None)

    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    _POOL_BY_DSN[dsn] = pool
    return pool


async def _run_query(*, cfg: PluginConfig, sql: str, args: list[Any] | None, max_rows: int | None) -> dict:
    _validate_sql(sql)

    max_rows_final = cfg.max_rows if max_rows is None else int(max_rows)
    max_rows_final = max(1, min(2000, max_rows_final))

    pool = await _get_pool(cfg.dsn)
    async with pool.acquire() as conn:
        try:
            # Make the connection read-only and set statement timeout.
            await conn.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
        except Exception:
            # Not all roles/settings allow this; it's best-effort.
            pass
        try:
            await conn.execute(f"SET statement_timeout = {cfg.statement_timeout_ms}")
        except Exception:
            pass

        rows = await conn.fetch(sql, *(args or []), timeout=cfg.timeout_seconds)

    out_rows: list[list[Any]] = []
    cols: list[str] = []

    if rows:
        cols = list(rows[0].keys())
        for r in rows[:max_rows_final]:
            out_rows.append([_to_jsonable(r.get(c)) for c in cols])

    return {
        "columns": cols,
        "rows": out_rows,
        "row_count": len(out_rows),
        "truncated": len(rows) > len(out_rows),
    }


def _tools_list() -> dict:
    return {
        "tools": [
            {
                "name": "query",
                "description": "Run a read-only SQL query (WITH/SELECT/SHOW/EXPLAIN).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string"},
                        "args": {"type": "array", "items": {}},
                        "max_rows": {"type": "integer", "minimum": 1, "maximum": 2000}
                    },
                    "required": ["sql"]
                },
            }
        ]
    }


def _tools_call(params: dict) -> dict:
    name = params.get("name")
    args = params.get("arguments") or {}
    context = params.get("context") or {}

    cfg = _load_config(context)

    if name != "query":
        raise ValueError(f"Unknown tool: {name}")

    sql = args.get("sql")
    if not isinstance(sql, str):
        raise ValueError("'sql' must be a string")

    q_args = args.get("args")
    if q_args is None:
        q_args_list: list[Any] | None = None
    elif isinstance(q_args, list):
        q_args_list = q_args
    else:
        raise ValueError("'args' must be an array")

    max_rows = args.get("max_rows")
    if max_rows is not None:
        try:
            max_rows_int: int | None = int(max_rows)
        except Exception:
            raise ValueError("'max_rows' must be an integer")
    else:
        max_rows_int = None

    return asyncio.run(_run_query(cfg=cfg, sql=sql, args=q_args_list, max_rows=max_rows_int))


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
                _ok(req_id, {"server": {"name": "postgres-query", "version": "0.1.0"}})
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
