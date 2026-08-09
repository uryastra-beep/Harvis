from __future__ import annotations

import threading
from collections.abc import Callable

from harvis.config import HarvisSettings
from harvis.core.command_parser import contains_wake_word, parse_spoken_intent
from harvis.core.intents import IntentType
from harvis.core.router import IntentRouter
from harvis.voice.sapi_listener import SapiSpeechListener
from harvis.voice.sapi_tts import SapiVoice


class HarvisAssistant:
    """Coordinate speech recognition, command routing, actions, and spoken feedback."""

    def __init__(
        self,
        settings: HarvisSettings,
        *,
        on_heard: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        self._settings = settings
        self._on_heard = on_heard
        self._on_status = on_status

        self._speaking_event = threading.Event()
        self._router = IntentRouter()

        self._voice = SapiVoice(
            volume=settings.voice_volume,
            on_speaking_changed=self._set_speaking,
            on_error=self._handle_voice_error,
        )
        self._listener = SapiSpeechListener(
            on_text=self._handle_recognition,
            should_ignore=self._speaking_event.is_set,
            on_ready=self._handle_listener_ready,
            on_error=self._handle_listener_error,
        )

    def start(self) -> None:
        self._notify_status("Starting voice assistant")
        self._voice.start()
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()
        self._voice.stop()
        self._notify_status("Voice assistant stopped")

    def apply_settings(self, settings: HarvisSettings) -> None:
        self._settings = settings
        self._voice.set_volume(settings.voice_volume)

    def speak(self, text: str) -> None:
        self._voice.speak(text)

    def _handle_listener_ready(self) -> None:
        self._notify_status("Listening for Harvis")
        self.speak("Harvis is online.")

    def _handle_recognition(self, text: str) -> None:
        if self._on_heard is not None:
            self._on_heard(text)

        if not contains_wake_word(text):
            return

        intent = parse_spoken_intent(text)
        if intent is None:
            self.speak("Yes?")
            return

        try:
            if intent.type is IntentType.ASK_AI:
                self.speak("AI answers are not configured yet.")
                return

            self._router.dispatch(intent)
            self._speak_success(intent)
        except Exception as exc:
            self._notify_status(f"Command failed: {exc}")
            self.speak("I could not complete that command.")

    def _speak_success(self, intent) -> None:
        if intent.type is IntentType.SET_VOLUME:
            percent = int(intent.parameters.get("percent", 0))
            self.speak(f"Volume set to {percent} percent.")
            return

        if intent.type is IntentType.OPEN_URL:
            target = str(intent.parameters.get("target", "it")).strip() or "it"
            self.speak(f"Opening {target}.")

    def _set_speaking(self, speaking: bool) -> None:
        if speaking:
            self._speaking_event.set()
            self._notify_status("Speaking")
        else:
            self._speaking_event.clear()
            if self._listener.is_ready:
                self._notify_status("Listening for Harvis")

    def _handle_listener_error(self, error: Exception) -> None:
        self._notify_status(f"Speech recognition unavailable: {error}")

    def _handle_voice_error(self, error: Exception) -> None:
        self._notify_status(f"Speech synthesis unavailable: {error}")

    def _notify_status(self, status: str) -> None:
        callback = self._on_status
        if callback is not None:
            callback(status)
