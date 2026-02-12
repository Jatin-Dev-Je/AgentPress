from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


IsolationMode = Literal["shared", "per-agent"]


@dataclass(frozen=True)
class PluginManifest:
    id: str
    name: str
    version: str
    description: str | None
    entrypoint: str
    transport: Literal["stdio"]
    isolation: IsolationMode = "shared"
    config_schema_path: str | None = None


@dataclass(frozen=True)
class PluginInfo:
    manifest: PluginManifest
    path: Path


ToolResult = dict[str, Any]
