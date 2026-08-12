from __future__ import annotations

import platform
import threading
from collections.abc import Callable

from harvis.core.command_parser import contains_wake_word


class LocalWakeWordController:
    """Use the operating system's local recognizer to detect Harvis/Jarvis."""

    def __init__(
        self,
        on_wake: Callable[[str], None],
        *,
        language_tag: str = "es-419",
        on_status: Callable[[str], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._on_wake = on_wake
        self._language_tag = language_tag
        self._on_status = on_status
        self._on_error = on_error
        self._listener = None
        self._lock = threading.RLock()

    @property
    def is_running(self) -> bool:
        with self._lock:
            listener = self._listener
        return bool(listener is not None and getattr(listener, "is_ready", False))

    def start(self) -> None:
        if platform.system() != "Windows":
            raise RuntimeError("Local wake-word detection currently requires Windows SAPI.")
        with self._lock:
            if self._listener is not None:
                return
            from harvis.voice.sapi_listener import SapiSpeechListener

            listener = SapiSpeechListener(
                self._handle_text,
                language_tag=self._language_tag,
                on_ready=lambda: self._notify_status("Waiting locally for Harvis or Jarvis"),
                on_error=self._handle_error,
            )
            self._listener = listener
            listener.start()

    def stop(self) -> None:
        with self._lock:
            listener = self._listener
            self._listener = None
        if listener is not None:
            listener.stop()

    def set_language(self, language_tag: str) -> None:
        self._language_tag = language_tag
        with self._lock:
            listener = self._listener
        if listener is not None:
            listener.set_language(language_tag)

    def _handle_text(self, text: str) -> None:
        if not contains_wake_word(text):
            return
        self.stop()
        self._notify_status("Local wake word detected")
        self._on_wake(text)

    def _handle_error(self, error: Exception) -> None:
        with self._lock:
            self._listener = None
        callback = self._on_error
        if callback is not None:
            callback(error)

    def _notify_status(self, status: str) -> None:
        callback = self._on_status
        if callback is not None:
            callback(status)


__all__ = ["LocalWakeWordController"]
