from __future__ import annotations

import io
import threading
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harvis.features.storage import harvis_data_dir, read_json, write_json

MAX_VISUAL_MEMORIES = 200
MIN_SUCCESSES_FOR_RECALL = 2
MIN_FINGERPRINT_SIMILARITY = 0.91
FINGERPRINT_SIZE = 12
PATCH_RADIUS_SCREEN_PIXELS = 36


def _normalize_target(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value))
    without_marks = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(without_marks.casefold().split())[:240]


class VisualTargetMemory:
    """Remember verified UI locations and reuse them only when pixels still match."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or harvis_data_dir() / "visual_memory.json"
        self._lock = threading.RLock()

    def remember(
        self,
        target: str,
        button: str,
        capture: Any,
        x: int,
        y: int,
        *,
        sensitive: bool = False,
    ) -> None:
        if sensitive:
            return
        key = self._key(target, button)
        if not key:
            return
        fingerprint = _capture_fingerprint(capture, int(x), int(y))
        if fingerprint is None:
            return
        geometry = _capture_geometry(capture)
        with self._lock:
            memories = self._load()
            previous = memories.get(key, {})
            memories[key] = {
                "target": " ".join(str(target).split())[:240],
                "button": str(button),
                "x": int(x),
                "y": int(y),
                "geometry": list(geometry),
                "fingerprint": fingerprint.hex(),
                "successes": max(0, int(previous.get("successes", 0))) + 1,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            if len(memories) > MAX_VISUAL_MEMORIES:
                oldest = sorted(
                    memories,
                    key=lambda item: str(memories[item].get("updated_at", "")),
                )[: len(memories) - MAX_VISUAL_MEMORIES]
                for old_key in oldest:
                    memories.pop(old_key, None)
            write_json(self.path, memories)

    def recall(
        self,
        target: str,
        button: str,
        capture: Any,
    ) -> dict[str, Any] | None:
        key = self._key(target, button)
        with self._lock:
            memory = self._load().get(key)
        if not isinstance(memory, dict):
            return None
        if int(memory.get("successes", 0)) < MIN_SUCCESSES_FOR_RECALL:
            return None
        geometry = _capture_geometry(capture)
        if list(geometry) != memory.get("geometry"):
            return None
        try:
            x = int(memory["x"])
            y = int(memory["y"])
            stored = bytes.fromhex(str(memory["fingerprint"]))
        except (KeyError, TypeError, ValueError):
            return None
        origin_x, origin_y, width, height = geometry
        if not origin_x <= x < origin_x + width or not origin_y <= y < origin_y + height:
            return None
        current = _capture_fingerprint(capture, x, y)
        if current is None or len(stored) != len(current) or not stored:
            return None
        difference = sum(abs(left - right) for left, right in zip(stored, current))
        similarity = 1.0 - difference / (255.0 * len(stored))
        if similarity < MIN_FINGERPRINT_SIMILARITY:
            return None
        return {
            "x": x,
            "y": y,
            "similarity": round(similarity, 3),
            "successes": int(memory.get("successes", 0)),
        }

    def stats(self) -> dict[str, Any]:
        with self._lock:
            memories = self._load()
        return {
            "status": "completed",
            "targets": len(memories),
            "reusable": sum(
                int(item.get("successes", 0)) >= MIN_SUCCESSES_FOR_RECALL
                for item in memories.values()
            ),
            "path": str(self.path),
        }

    def clear(self) -> dict[str, Any]:
        with self._lock:
            write_json(self.path, {})
        return {"status": "cleared", "path": str(self.path)}

    @staticmethod
    def _key(target: str, button: str) -> str:
        normalized_target = _normalize_target(target)
        normalized_button = str(button).strip().casefold()
        if not normalized_target or normalized_button not in {
            "left",
            "right",
            "double_left",
        }:
            return ""
        return f"{normalized_button}:{normalized_target}"

    def _load(self) -> dict[str, dict[str, Any]]:
        payload = read_json(self.path, {})
        if not isinstance(payload, dict):
            return {}
        return {
            str(key): value
            for key, value in payload.items()
            if isinstance(value, dict)
        }


def _capture_geometry(capture: Any) -> tuple[int, int, int, int]:
    return (
        int(capture.origin_x),
        int(capture.origin_y),
        int(capture.width),
        int(capture.height),
    )


def _capture_fingerprint(capture: Any, screen_x: int, screen_y: int) -> bytes | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(io.BytesIO(capture.image_bytes)) as source:
            image = source.convert("L")
            scale_x = image.width / max(1, int(capture.width))
            scale_y = image.height / max(1, int(capture.height))
            center_x = (int(screen_x) - int(capture.origin_x)) * scale_x
            center_y = (int(screen_y) - int(capture.origin_y)) * scale_y
            radius_x = max(8, int(PATCH_RADIUS_SCREEN_PIXELS * scale_x))
            radius_y = max(8, int(PATCH_RADIUS_SCREEN_PIXELS * scale_y))
            left = max(0, int(center_x) - radius_x)
            top = max(0, int(center_y) - radius_y)
            right = min(image.width, int(center_x) + radius_x)
            bottom = min(image.height, int(center_y) + radius_y)
            if right - left < 4 or bottom - top < 4:
                return None
            reduced = image.crop((left, top, right, bottom)).resize(
                (FINGERPRINT_SIZE, FINGERPRINT_SIZE)
            )
            return reduced.tobytes()
    except (OSError, ValueError):
        return None


__all__ = [
    "MAX_VISUAL_MEMORIES",
    "MIN_FINGERPRINT_SIMILARITY",
    "MIN_SUCCESSES_FOR_RECALL",
    "VisualTargetMemory",
]
