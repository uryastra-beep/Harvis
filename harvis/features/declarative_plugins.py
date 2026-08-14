from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from harvis.features.storage import atomic_write_text, harvis_data_dir

MAX_PLUGIN_ACTIONS = 24
MAX_PLUGIN_FILE_BYTES = 256_000
_DEFAULT_PLUGINS = {
    "spotify.json": {
        "name": "Spotify",
        "description": "Open Spotify and start or pause media playback.",
        "steps": [
            {"action": "open_application", "app_name": "Spotify"},
            {"action": "wait", "seconds": 1.0},
            {"action": "media_control", "media_action": "play_pause"},
        ],
    },
    "discord.json": {
        "name": "Discord",
        "description": "Open the Discord desktop application.",
        "steps": [{"action": "open_application", "app_name": "Discord"}],
    },
    "github.json": {
        "name": "GitHub",
        "description": "Open GitHub in the default browser.",
        "steps": [{"action": "open_url", "url": "https://github.com/"}],
    },
    "gmail.json": {
        "name": "Gmail",
        "description": "Open Gmail in the default browser.",
        "steps": [{"action": "open_url", "url": "https://mail.google.com/"}],
    },
    "calendar.json": {
        "name": "Google Calendar",
        "description": "Open Google Calendar in the default browser.",
        "steps": [{"action": "open_url", "url": "https://calendar.google.com/"}],
    },
}


class DeclarativePluginStore:
    """Load data-only Harvis skills without executing arbitrary Python code."""

    def __init__(self, directory: Path | None = None) -> None:
        self._seed_defaults = directory is None
        self.directory = directory or harvis_data_dir() / "plugins"
        if self._seed_defaults:
            self._ensure_default_plugins()

    def list(self) -> dict[str, Any]:
        plugins = self._load_all()
        return {
            "status": "completed",
            "count": len(plugins),
            "plugins": [
                {
                    "name": plugin["name"],
                    "description": plugin.get("description", ""),
                    "version": plugin.get("version", "1.0.0"),
                    "author": plugin.get("author", ""),
                    "actions": len(plugin["steps"]),
                }
                for plugin in plugins.values()
            ],
            "directory": str(self.directory),
        }

    def get(self, name: str) -> dict[str, Any] | None:
        return self._load_all().get(" ".join(str(name).split()).casefold())

    def install(
        self,
        source: str | Path,
        *,
        validate_steps: Callable[[list[dict[str, Any]]], Any] | None = None,
    ) -> dict[str, Any]:
        source_path = Path(source).expanduser().resolve()
        if source_path.suffix.casefold() != ".json" or not source_path.is_file():
            raise ValueError("A Harvis plugin must be an existing JSON file.")
        if source_path.stat().st_size > MAX_PLUGIN_FILE_BYTES:
            raise ValueError("The plugin file is too large.")
        plugin = self._read_plugin(source_path)
        if plugin is None:
            raise ValueError("The plugin manifest is invalid.")
        steps = plugin["steps"]
        if validate_steps is not None:
            validate_steps(steps)

        file_name = re.sub(r"[^a-z0-9]+", "-", plugin["name"].casefold()).strip("-")
        if not file_name:
            raise ValueError("The plugin name cannot be converted to a safe file name.")
        destination = self.directory / f"{file_name[:80]}.json"
        self.directory.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            return {
                "status": "already_exists",
                "name": plugin["name"],
                "path": str(destination),
                "message": "Remove the installed plugin before replacing it.",
            }
        atomic_write_text(
            destination,
            json.dumps(plugin, indent=2, ensure_ascii=False) + "\n",
        )
        return {
            "status": "installed",
            "name": plugin["name"],
            "version": plugin.get("version", "1.0.0"),
            "path": str(destination),
            "actions": len(steps),
        }

    def remove(self, name: str) -> dict[str, Any]:
        clean_name = " ".join(str(name).split()).strip()
        plugins = self._load_all(include_path=True)
        plugin = plugins.get(clean_name.casefold())
        if plugin is None:
            return {"status": "not_found", "name": clean_name}
        path = plugin.get("_path")
        if not isinstance(path, Path):
            return {"status": "not_found", "name": clean_name}
        try:
            path.unlink()
        except OSError as exc:
            raise OSError(f"Harvis could not remove plugin {clean_name}.") from exc
        return {"status": "removed", "name": plugin["name"]}

    def _load_all(self, *, include_path: bool = False) -> dict[str, dict[str, Any]]:
        plugins: dict[str, dict[str, Any]] = {}
        for path in sorted(self.directory.glob("*.json")):
            payload = self._read_plugin(path)
            if payload is None:
                continue
            if include_path:
                payload["_path"] = path
            plugins[payload["name"].casefold()] = payload
        return plugins

    @staticmethod
    def _read_plugin(path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        name = " ".join(str(payload.get("name", "")).split()).strip()[:80]
        steps = payload.get("steps")
        if (
            not name
            or not isinstance(steps, list)
            or not 1 <= len(steps) <= MAX_PLUGIN_ACTIONS
            or not all(isinstance(step, dict) for step in steps)
        ):
            return None
        return {
            "name": name,
            "description": str(payload.get("description", "")).strip()[:240],
            "version": " ".join(str(payload.get("version", "1.0.0")).split())[:32],
            "author": " ".join(str(payload.get("author", "")).split())[:80],
            "steps": steps,
        }

    def _ensure_default_plugins(self) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        for file_name, payload in _DEFAULT_PLUGINS.items():
            path = self.directory / file_name
            if path.exists():
                continue
            try:
                atomic_write_text(
                    path,
                    json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                )
            except OSError:
                continue
