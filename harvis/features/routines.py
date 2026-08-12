from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harvis.features.storage import harvis_data_dir, read_json, write_json

MAX_ROUTINES = 50


class RoutineStore:
    """Persist user-named guarded action plans."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or harvis_data_dir() / "routines.json"
        self._lock = threading.RLock()

    @staticmethod
    def _clean_name(name: str) -> str:
        return " ".join(str(name).split()).strip()[:80]

    def save(self, name: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
        clean_name = self._clean_name(name)
        if not clean_name:
            raise ValueError("A routine name is required.")
        if not isinstance(steps, list) or not steps:
            raise ValueError("A routine requires at least one action.")

        with self._lock:
            routines = self._load()
            key = clean_name.casefold()
            if key not in routines and len(routines) >= MAX_ROUTINES:
                raise ValueError(f"Harvis supports at most {MAX_ROUTINES} routines.")
            routines[key] = {
                "name": clean_name,
                "steps": steps,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            write_json(self.path, routines)
        return {"status": "saved", "name": clean_name, "steps": len(steps)}

    def get(self, name: str) -> dict[str, Any] | None:
        clean_name = self._clean_name(name)
        with self._lock:
            routine = self._load().get(clean_name.casefold())
        return routine if isinstance(routine, dict) else None

    def list(self) -> dict[str, Any]:
        with self._lock:
            routines = self._load()
        items = [
            {
                "name": str(routine.get("name", key)),
                "steps": len(routine.get("steps", [])),
                "updated_at": str(routine.get("updated_at", "")),
            }
            for key, routine in routines.items()
            if isinstance(routine, dict)
        ]
        items.sort(key=lambda item: item["name"].casefold())
        return {"status": "completed", "count": len(items), "routines": items}

    def delete(self, name: str) -> dict[str, Any]:
        clean_name = self._clean_name(name)
        with self._lock:
            routines = self._load()
            removed = routines.pop(clean_name.casefold(), None)
            if removed is not None:
                write_json(self.path, routines)
        return {
            "status": "deleted" if removed is not None else "not_found",
            "name": clean_name,
        }

    def _load(self) -> dict[str, dict[str, Any]]:
        payload = read_json(self.path, {})
        return payload if isinstance(payload, dict) else {}
