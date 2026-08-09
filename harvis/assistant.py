from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from harvis.config import HarvisSettings
from harvis.core.intents import Intent, IntentType
from harvis.core.router import IntentRouter
from harvis.voice.gemini_live import GeminiLiveVoice


class HarvisAssistant:
    """Coordinate Gemini Live voice, local tools, and application status."""

    def __init__(
        self,
        settings: HarvisSettings,
        *,
        on_heard: Callable[[str], None] | None = None,
        on_response: Callable[[str], None] | None = None,
        on_audio_level: Callable[[float], None] | None = None,
        on_spectrum: Callable[[list[float] | None], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        self._settings = settings
        self._on_heard = on_heard
        self._on_response = on_response
        self._on_audio_level = on_audio_level
        self._on_spectrum = on_spectrum
        self._on_status = on_status
        self._router = IntentRouter()

        self._voice = GeminiLiveVoice(
            language_tag=settings.speech_language,
            voice_volume=settings.voice_volume,
            execute_tool=self._execute_tool,
            on_input_transcript=self._handle_input_transcript,
            on_output_transcript=self._handle_output_transcript,
            on_audio_level=self._handle_audio_level,
            on_spectrum=self._handle_spectrum,
            on_ready=self._handle_live_ready,
            on_status=self._notify_status,
            on_error=self._handle_live_error,
        )

    def start(self) -> None:
        self._notify_status("Starting Gemini Live voice assistant")
        self._voice.start()

    def stop(self) -> None:
        self._voice.stop()
        self._notify_status("Voice assistant stopped")

    def apply_settings(self, settings: HarvisSettings) -> None:
        previous_language = self._settings.speech_language
        self._settings = settings
        self._voice.set_volume(settings.voice_volume)

        if settings.speech_language != previous_language:
            self._notify_status(
                f"Switching preferred speech language to {settings.speech_language}"
            )
            self._voice.set_language(settings.speech_language)

    def _handle_live_ready(self) -> None:
        self._notify_status(
            f"Listening with Gemini Live ({self._voice.language_tag})"
        )

    def _handle_input_transcript(self, text: str) -> None:
        callback = self._on_heard
        if callback is not None:
            callback(text)

    def _handle_output_transcript(self, text: str) -> None:
        callback = self._on_response
        if callback is not None:
            callback(text)

    def _handle_audio_level(self, level: float) -> None:
        callback = self._on_audio_level
        if callback is not None:
            callback(level)

    def _handle_spectrum(self, spectrum: list[float] | None) -> None:
        callback = self._on_spectrum
        if callback is not None:
            callback(spectrum)

    def _handle_live_error(self, error: Exception) -> None:
        self._notify_status(f"Gemini Live unavailable: {error}")

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "set_master_volume":
            if "percent" not in arguments:
                raise ValueError("set_master_volume requires percent.")

            percent = max(0, min(100, int(arguments["percent"])))
            self._router.dispatch(
                Intent(
                    IntentType.SET_VOLUME,
                    {"percent": percent},
                )
            )
            return {
                "status": "completed",
                "percent": percent,
            }

        if name == "open_url":
            url = str(arguments.get("url", "")).strip()
            parsed = urlparse(url)

            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("open_url requires a complete HTTP or HTTPS URL.")

            self._router.dispatch(
                Intent(
                    IntentType.OPEN_URL,
                    {"url": url},
                )
            )
            return {
                "status": "completed",
                "url": url,
            }

        raise ValueError(f"Unsupported Harvis tool: {name}")

    def _notify_status(self, status: str) -> None:
        callback = self._on_status
        if callback is not None:
            callback(status)
