from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SUPPORTED_SPEECH_LANGUAGES = {
    "es-419": "Spanish (Latin America)",
    "en-US": "English (United States)",
}
SUPPORTED_ASSISTANT_MODES = ("Speaking", "Silent")
USER_NAME_MAX_LENGTH = 48
REMOTE_CONTROL_PORT_MIN = 1024
REMOTE_CONTROL_PORT_MAX = 65535


@dataclass(slots=True)
class HarvisSettings:
    start_with_windows: bool = False
    user_name: str = "User"
    assistant_mode: str = "Speaking"
    voice_volume: int = 70
    microphone_device: str = "System default"
    speech_language: str = "es-419"
    visualizer_enabled: bool = True
    visualizer_type: str = "Sphere"
    visualizer_sensitivity: int = 60
    ai_provider: str = "Gemini Live"
    ai_watermark_enabled: bool = True
    remote_control_enabled: bool = False
    remote_control_port: int = 8765

    def normalized(self) -> HarvisSettings:
        normalized_name = " ".join(str(self.user_name).split()).strip()
        self.user_name = normalized_name[:USER_NAME_MAX_LENGTH] or "User"
        self.voice_volume = max(0, min(100, int(self.voice_volume)))
        self.visualizer_sensitivity = max(0, min(100, int(self.visualizer_sensitivity)))

        if self.assistant_mode not in SUPPORTED_ASSISTANT_MODES:
            self.assistant_mode = "Speaking"

        if self.speech_language not in SUPPORTED_SPEECH_LANGUAGES:
            self.speech_language = "es-419"

        if self.visualizer_type not in {"Sphere", "Bars"}:
            self.visualizer_type = "Sphere"

        if not isinstance(self.ai_watermark_enabled, bool):
            self.ai_watermark_enabled = True

        if not isinstance(self.remote_control_enabled, bool):
            self.remote_control_enabled = False

        try:
            remote_port = int(self.remote_control_port)
        except (TypeError, ValueError):
            remote_port = 8765
        self.remote_control_port = max(
            REMOTE_CONTROL_PORT_MIN,
            min(REMOTE_CONTROL_PORT_MAX, remote_port),
        )

        return self


class SettingsStore:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or self._default_config_path()

    @staticmethod
    def _default_config_path() -> Path:
        app_data = os.getenv("APPDATA")
        base_path = Path(app_data) if app_data else Path.home() / ".config"
        return base_path / "Harvis" / "settings.json"

    def load(self) -> HarvisSettings:
        if not self.config_path.exists():
            return HarvisSettings()

        try:
            raw_data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return HarvisSettings()

        if not isinstance(raw_data, dict):
            return HarvisSettings()

        valid_fields = HarvisSettings.__dataclass_fields__.keys()
        filtered_data: dict[str, Any] = {
            key: value for key, value in raw_data.items() if key in valid_fields
        }

        try:
            return HarvisSettings(**filtered_data).normalized()
        except (TypeError, ValueError):
            return HarvisSettings()

    def save(self, settings: HarvisSettings) -> None:
        normalized = settings.normalized()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(normalized), indent=2, ensure_ascii=True) + "\n"
        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{self.config_path.name}.",
                suffix=".tmp",
                dir=self.config_path.parent,
                text=True,
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self.config_path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                with contextlib.suppress(OSError):
                    temporary_path.unlink(missing_ok=True)
