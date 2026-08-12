from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harvis.features.storage import harvis_data_dir, read_json, write_json

MAX_MEMORIES = 250
MAX_KEY_CHARACTERS = 120
MAX_VALUE_CHARACTERS = 2000
_SECRET_MARKERS = (
    "api key",
    "apikey",
    "password",
    "passwd",
    "token",
    "secret",
    "contraseña",
    "clave privada",
)


class MemoryStore:
    """Small user-controlled local memory store."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or harvis_data_dir() / "memory.json"
        self._lock = threading.RLock()

    @staticmethod
    def _clean_key(key: str) -> str:
        return " ".join(str(key).split()).strip()[:MAX_KEY_CHARACTERS]

    @staticmethod
    def _clean_value(value: str) -> str:
        return str(value).strip()[:MAX_VALUE_CHARACTERS]

    @staticmethod
    def _normalized(value: str) -> str:
        return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())

    def remember(self, key: str, value: str) -> dict[str, Any]:
        clean_key = self._clean_key(key)
        clean_value = self._clean_value(value)
        if not clean_key or not clean_value:
            raise ValueError("Memory key and value are required.")

        combined = self._normalized(f"{clean_key} {clean_value}")
        if any(marker in combined for marker in _SECRET_MARKERS):
            raise ValueError("Harvis does not store passwords, API keys, tokens, or secrets in memory.")

        with self._lock:
            entries = self._load()
            normalized_key = self._normalized(clean_key)
            entries = [
                entry
                for entry in entries
                if self._normalized(str(entry.get("key", ""))) != normalized_key
            ]
            entries.append(
                {
                    "key": clean_key,
                    "value": clean_value,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            if len(entries) > MAX_MEMORIES:
                entries = entries[-MAX_MEMORIES:]
            write_json(self.path, entries)

        return {"status": "remembered", "key": clean_key}

    def recall(self, query: str = "", *, limit: int = 10) -> dict[str, Any]:
        normalized_query = self._normalized(str(query))
        terms = normalized_query.split()
        with self._lock:
            entries = list(reversed(self._load()))

        if terms:
            entries = [
                entry
                for entry in entries
                if all(
                    term
                    in self._normalized(
                        f"{entry.get('key', '')} {entry.get('value', '')}"
                    )
                    for term in terms
                )
            ]

        bounded_limit = max(1, min(25, int(limit)))
        matches = entries[:bounded_limit]
        return {
            "status": "completed",
            "query": str(query).strip(),
            "count": len(matches),
            "memories": matches,
        }

    def forget(self, key: str) -> dict[str, Any]:
        clean_key = self._clean_key(key)
        normalized_key = self._normalized(clean_key)
        if not normalized_key:
            raise ValueError("A memory key is required.")

        with self._lock:
            entries = self._load()
            remaining = [
                entry
                for entry in entries
                if self._normalized(str(entry.get("key", ""))) != normalized_key
            ]
            removed = len(entries) - len(remaining)
            if removed:
                write_json(self.path, remaining)

        return {
            "status": "forgotten" if removed else "not_found",
            "key": clean_key,
        }

    def _load(self) -> list[dict[str, str]]:
        payload = read_json(self.path, [])
        if not isinstance(payload, list):
            return []
        return [entry for entry in payload if isinstance(entry, dict)]
