import json
from pathlib import Path

from app.plugins.models import PluginInfo, PluginManifest


class PluginRegistry:
    def __init__(self, plugins_dir: Path):
        self._plugins_dir = plugins_dir

    async def list_installed(self) -> list[PluginInfo]:
        if not self._plugins_dir.exists():
            return []

        plugins: list[PluginInfo] = []
        for child in sorted(self._plugins_dir.iterdir()):
            if not child.is_dir():
                continue
            manifest_path = child / "plugin.json"
            if not manifest_path.exists():
                continue
            plugins.append(PluginInfo(path=child, manifest=self._load_manifest(manifest_path)))
        return plugins

    def get_plugin_path(self, plugin_id: str) -> Path:
        return self._plugins_dir / plugin_id

    def load_manifest(self, plugin_id: str) -> PluginManifest:
        manifest_path = self.get_plugin_path(plugin_id) / "plugin.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Plugin '{plugin_id}' not found in {self._plugins_dir}")
        return self._load_manifest(manifest_path)

    def _load_manifest(self, manifest_path: Path) -> PluginManifest:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        mcp = data.get("mcp") or {}
        transport = mcp.get("transport") or "stdio"

        return PluginManifest(
            id=data["id"],
            name=data.get("name") or data["id"],
            version=data.get("version") or "0.0.0",
            description=data.get("description"),
            entrypoint=data.get("entrypoint") or "main.py",
            transport=transport,
            isolation=data.get("isolation") or "shared",
            config_schema_path=data.get("config_schema"),
        )
