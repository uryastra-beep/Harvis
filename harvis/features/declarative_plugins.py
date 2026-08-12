from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harvis.features.storage import atomic_write_text, harvis_data_dir

MAX_PLUGIN_ACTIONS = 24
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
                    "actions": len(plugin["steps"]),
                }
                for plugin in plugins.values()
            ],
            "directory": str(self.directory),
        }

    def get(self, name: str) -> dict[str, Any] | None:
        return self._load_all().get(" ".join(str(name).split()).casefold())

    def _load_all(self) -> dict[str, dict[str, Any]]:
        plugins: dict[str, dict[str, Any]] = {}
        for path in sorted(self.directory.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            name = " ".join(str(payload.get("name", "")).split()).strip()[:80]
            steps = payload.get("steps")
            if not name or not isinstance(steps, list) or not 1 <= len(steps) <= MAX_PLUGIN_ACTIONS:
                continue
            plugins[name.casefold()] = {
                "name": name,
                "description": str(payload.get("description", "")).strip()[:240],
                "steps": steps,
            }
        return plugins

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
