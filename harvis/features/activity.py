from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harvis.features.storage import atomic_write_text, harvis_data_dir

MAX_ACTIVITY_ENTRIES = 500


class ActivityHistory:
    """Bounded local audit history with deliberately limited undo metadata."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or harvis_data_dir() / "activity.jsonl"
        self._lock = threading.RLock()
        self._undo_stack: deque[dict[str, Any]] = deque(maxlen=25)

    def record(
        self,
        action: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        *,
        undo: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "at": datetime.now(timezone.utc).isoformat(),
            "action": str(action),
            "arguments": self._redact(arguments),
            "status": str(result.get("status", "completed")),
        }
        with self._lock:
            entries = self._read_entries()
            entries.append(entry)
            entries = entries[-MAX_ACTIVITY_ENTRIES:]
            try:
                atomic_write_text(
                    self.path,
                    "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in entries),
                )
            except OSError:
                # Activity logging is best effort and must never break the
                # desktop action that the user requested.
                pass
            if undo is not None and entry["status"] == "completed":
                self._undo_stack.append(dict(undo))

    def recent(self, *, limit: int = 20) -> dict[str, Any]:
        bounded = max(1, min(100, int(limit)))
        with self._lock:
            entries = self._read_entries()[-bounded:]
        return {
            "status": "completed",
            "count": len(entries),
            "entries": list(reversed(entries)),
        }

    def take_undo(self) -> dict[str, Any] | None:
        with self._lock:
            return self._undo_stack.pop() if self._undo_stack else None

    def _read_entries(self) -> list[dict[str, Any]]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        entries: list[dict[str, Any]] = []
        for line in lines[-MAX_ACTIVITY_ENTRIES:]:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                entries.append(value)
        return entries

    @staticmethod
    def _redact(arguments: dict[str, Any]) -> dict[str, Any]:
        redacted: dict[str, Any] = {}
        for key, value in arguments.items():
            if any(marker in key.casefold() for marker in ("key", "password", "secret", "token")):
                redacted[key] = "<redacted>"
            elif key in {"text", "lines", "value"}:
                redacted[key] = "<content omitted>"
            else:
                redacted[key] = value
        return redacted
