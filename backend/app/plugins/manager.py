from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
import logging

from app.core.settings import settings
from app.plugins.models import PluginManifest
from app.plugins.registry import PluginRegistry
from app.plugins.stdio_client import StdioMcpClient


logger = logging.getLogger(__name__)


@dataclass
class AuditEvent:
    ts_ms: int
    plugin_id: str
    agent_id: str
    tool_name: str
    params_sha256: str
    ok: bool


class PluginManager:
    def __init__(self, plugins_dir: Path):
        self._registry = PluginRegistry(plugins_dir)
        self._clients: dict[str, StdioMcpClient] = {}
        self._audit: list[AuditEvent] = []

    async def list_plugins(self) -> list[dict]:
        installed = await self._registry.list_installed()
        out: list[dict] = []
        for p in installed:
            tools: list[dict] = []
            try:
                client = self._get_or_create_client(p.manifest, agent_id=None)
                tools = await client.list_tools()
            except Exception:
                logger.exception("Failed to list tools for plugin '%s'", p.manifest.id)
                tools = []
            out.append(
                {
                    "id": p.manifest.id,
                    "name": p.manifest.name,
                    "version": p.manifest.version,
                    "isolation": p.manifest.isolation,
                    "tools": tools,
                }
            )
        return out

    async def restart_plugin(self, plugin_id: str) -> None:
        keys = [k for k in self._clients.keys() if k == plugin_id or k.startswith(plugin_id + ":")]
        for key in keys:
            await self._clients[key].stop()
            del self._clients[key]

    async def call_tool(self, plugin_id: str, tool_name: str, params: dict, agent_id: str) -> dict:
        manifest = self._registry.load_manifest(plugin_id)
        client = self._get_or_create_client(manifest, agent_id=agent_id)

        context = {"agent_id": agent_id}

        params_hash = hashlib.sha256(json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()
        start_ms = int(time.time() * 1000)
        ok = True
        try:
            result = await client.call_tool(tool_name=tool_name, params=params, context=context)
            return {"result": result}
        except Exception:
            ok = False
            raise
        finally:
            self._audit.append(
                AuditEvent(
                    ts_ms=start_ms,
                    plugin_id=plugin_id,
                    agent_id=agent_id,
                    tool_name=tool_name,
                    params_sha256=params_hash,
                    ok=ok,
                )
            )

    def _get_or_create_client(self, manifest: PluginManifest, agent_id: str | None) -> StdioMcpClient:
        key = manifest.id
        if manifest.isolation == "per-agent" and agent_id:
            key = f"{manifest.id}:{agent_id}"

        existing = self._clients.get(key)
        if existing is not None:
            return existing

        plugin_path = self._registry.get_plugin_path(manifest.id)
        client = StdioMcpClient(
            plugin_path=plugin_path,
            entrypoint=manifest.entrypoint,
            timeout_seconds=settings.plugin_timeout_seconds,
            max_output_bytes=settings.plugin_max_output_bytes,
        )
        self._clients[key] = client
        return client


plugin_manager = PluginManager(settings.plugins_dir)
