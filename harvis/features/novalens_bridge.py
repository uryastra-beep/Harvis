from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from harvis.features.storage import atomic_write_text

BRIDGE_REQUEST_NAME = "harvis_bridge_request.json"
BRIDGE_RESPONSE_NAME = "harvis_bridge_response.json"
MAX_BRIDGE_TEXT_CHARACTERS = 20_000


class NovaLensBridge:
    """Exchange bounded local JSON messages with a resident NovaLens process."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or self._default_directory()
        self.request_path = self.directory / BRIDGE_REQUEST_NAME
        self.response_path = self.directory / BRIDGE_RESPONSE_NAME

    @staticmethod
    def _default_directory() -> Path:
        app_data = os.getenv("APPDATA")
        base = Path(app_data) if app_data else Path.home() / ".config"
        return base / "NovaLens"

    def send(
        self,
        action: str,
        *,
        text: str = "",
        wait_for_response: bool = False,
        timeout_seconds: float = 90.0,
    ) -> dict[str, Any]:
        normalized_action = str(action).strip().casefold()
        if normalized_action not in {"open", "ask", "screen", "audio"}:
            raise ValueError("Unsupported NovaLens bridge action.")
        clean_text = str(text).strip()[:MAX_BRIDGE_TEXT_CHARACTERS]
        if normalized_action == "ask" and not clean_text:
            raise ValueError("A question is required for the NovaLens bridge.")

        self.directory.mkdir(parents=True, exist_ok=True)
        request_id = str(time.time_ns())
        atomic_write_text(
            self.request_path,
            json.dumps(
                {
                    "version": 1,
                    "id": request_id,
                    "action": normalized_action,
                    "text": clean_text,
                    "created_at": time.time(),
                },
                ensure_ascii=False,
            ),
        )
        if not wait_for_response:
            return {
                "status": "sent",
                "action": normalized_action,
                "request_id": request_id,
            }

        deadline = time.monotonic() + max(5.0, min(180.0, float(timeout_seconds)))
        while time.monotonic() < deadline:
            time.sleep(0.2)
            try:
                payload = json.loads(self.response_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict) or str(payload.get("id", "")) != request_id:
                continue
            response_text = str(payload.get("text", ""))[:MAX_BRIDGE_TEXT_CHARACTERS]
            return {
                "status": str(payload.get("status", "completed")),
                "action": normalized_action,
                "request_id": request_id,
                "text": response_text,
            }
        return {
            "status": "timeout",
            "action": normalized_action,
            "request_id": request_id,
            "message": "NovaLens did not return a bridge response before the timeout.",
        }


__all__ = [
    "BRIDGE_REQUEST_NAME",
    "BRIDGE_RESPONSE_NAME",
    "MAX_BRIDGE_TEXT_CHARACTERS",
    "NovaLensBridge",
]
