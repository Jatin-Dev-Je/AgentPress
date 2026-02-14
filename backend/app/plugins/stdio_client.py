from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class StdioProcess:
    process: asyncio.subprocess.Process
    lock: asyncio.Lock


class StdioMcpClient:
    def __init__(
        self,
        plugin_path: Path,
        entrypoint: str,
        *,
        timeout_seconds: int,
        max_output_bytes: int,
        env_allowlist: dict[str, str] | None = None,
    ):
        self._plugin_path = plugin_path
        self._entrypoint = entrypoint
        self._timeout_seconds = timeout_seconds
        self._max_output_bytes = max_output_bytes
        self._env_allowlist = env_allowlist or {}

        self._proc: StdioProcess | None = None

    async def ensure_started(self) -> None:
        if self._proc and self._proc.process.returncode is None:
            return

        python_exe = sys.executable
        entry_file = self._resolve_entrypoint(self._entrypoint)

        # IMPORTANT: On Windows, providing a minimal env can break process startup
        # (e.g. missing SystemRoot). Inherit the current environment and only
        # override what we need.
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        env.update(self._env_allowlist)

        # Do not leak Agentpress secrets into untrusted plugin processes.
        # Keep the rest of the OS environment to avoid breaking process startup on Windows.
        for k in list(env.keys()):
            if k.startswith("AGENTPRESS_") and k not in self._env_allowlist:
                env.pop(k, None)
        env.pop("OPENAI_API_KEY", None)
        env.pop("ANTHROPIC_API_KEY", None)

        kwargs: dict[str, Any] = {}
        if os.name != "nt":
            try:
                import resource  # type: ignore

                def _limit() -> None:
                    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))

                kwargs["preexec_fn"] = _limit
            except Exception:
                pass

        process = await asyncio.create_subprocess_exec(
            python_exe,
            str(entry_file),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self._plugin_path),
            env=env,
            **kwargs,
        )

        self._proc = StdioProcess(process=process, lock=asyncio.Lock())

        await self._initialize()

    async def stop(self) -> None:
        if not self._proc:
            return
        proc = self._proc.process
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2)
            except TimeoutError:
                proc.kill()
        self._proc = None

    async def call_tool(self, tool_name: str, params: dict, context: dict) -> dict:
        await self.ensure_started()
        assert self._proc is not None

        request_id = uuid.uuid4().hex
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params,
                "context": context,
            },
        }

        async with self._proc.lock:
            await self._write_json_line(request)
            response = await self._read_json_line()

        if response.get("id") != request_id:
            raise RuntimeError("Plugin response id mismatch")
        if "error" in response and response["error"] is not None:
            raise RuntimeError(f"Plugin error: {response['error']}")
        return response.get("result") or {}

    async def list_tools(self) -> list[dict]:
        await self.ensure_started()
        assert self._proc is not None

        request_id = uuid.uuid4().hex
        request = {"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}}
        async with self._proc.lock:
            await self._write_json_line(request)
            response = await self._read_json_line()

        if response.get("id") != request_id:
            raise RuntimeError("Plugin response id mismatch")
        if "error" in response and response["error"] is not None:
            raise RuntimeError(f"Plugin error: {response['error']}")
        result = response.get("result") or {}
        return result.get("tools") or []

    async def _initialize(self) -> None:
        request_id = uuid.uuid4().hex
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {"client": {"name": "agentpress", "version": "0.1.0"}},
        }
        async with self._proc.lock:  # type: ignore[union-attr]
            await self._write_json_line(request)
            response = await self._read_json_line()
        if response.get("id") != request_id:
            raise RuntimeError("Plugin initialize id mismatch")

    async def _write_json_line(self, obj: dict) -> None:
        assert self._proc is not None
        data = (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")
        stdin = self._proc.process.stdin
        if stdin is None:
            raise RuntimeError("Plugin stdin not available")
        stdin.write(data)
        await stdin.drain()

    async def _read_json_line(self) -> dict:
        assert self._proc is not None
        stdout = self._proc.process.stdout
        if stdout is None:
            raise RuntimeError("Plugin stdout not available")

        try:
            line = await asyncio.wait_for(stdout.readline(), timeout=self._timeout_seconds)
        except asyncio.TimeoutError as e:
            raise TimeoutError("Plugin call timed out") from e

        if not line:
            stderr_tail = await self._read_stderr_tail()
            raise RuntimeError(f"Plugin exited unexpectedly. stderr: {stderr_tail}")

        if len(line) > self._max_output_bytes:
            raise RuntimeError("Plugin response too large")

        return json.loads(line.decode("utf-8"))

    async def _read_stderr_tail(self) -> str:
        assert self._proc is not None
        stderr = self._proc.process.stderr
        if stderr is None:
            return ""
        try:
            data = await asyncio.wait_for(stderr.read(4096), timeout=0.1)
        except Exception:
            return ""
        return data.decode("utf-8", errors="replace")

    def _resolve_entrypoint(self, entrypoint: str) -> Path:
        entry = Path(entrypoint)
        if entry.is_absolute():
            raise ValueError("Plugin entrypoint must be a relative path")

        resolved = (self._plugin_path / entry).resolve()
        try:
            if not resolved.is_relative_to(self._plugin_path.resolve()):
                raise ValueError("Plugin entrypoint escapes plugin directory")
        except AttributeError:
            # Python <3.9 fallback (not expected on CI, but safe).
            plugin_root = str(self._plugin_path.resolve())
            if not str(resolved).startswith(plugin_root):
                raise ValueError("Plugin entrypoint escapes plugin directory")

        return resolved
