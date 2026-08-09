from __future__ import annotations

import queue
import threading
from collections.abc import Callable

from comtypes import CoInitialize, CoUninitialize
from comtypes.client import CreateObject


class SapiVoice:
    """Speak queued text through the Windows SAPI voice engine."""

    def __init__(
        self,
        volume: int = 70,
        *,
        on_speaking_changed: Callable[[bool], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._volume = max(0, min(100, int(volume)))
        self._on_speaking_changed = on_speaking_changed
        self._on_error = on_error

        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker,
            name="HarvisSapiVoice",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._queue.put(None)

        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)

        self._thread = None

    def set_volume(self, volume: int) -> None:
        self._volume = max(0, min(100, int(volume)))

    def speak(self, text: str) -> None:
        cleaned = str(text).strip()
        if not cleaned:
            return

        if self._thread is None or not self._thread.is_alive():
            self.start()

        self._queue.put(cleaned)

    def _worker(self) -> None:
        CoInitialize()
        speaker = None

        try:
            speaker = CreateObject("SAPI.SpVoice")

            while not self._stop_event.is_set():
                text = self._queue.get()
                if text is None:
                    break

                try:
                    speaker.Volume = self._volume
                    self._notify_speaking(True)
                    speaker.Speak(text, 0)
                except Exception as exc:
                    self._notify_error(exc)
                finally:
                    self._notify_speaking(False)
        except Exception as exc:
            self._notify_error(exc)
        finally:
            speaker = None
            CoUninitialize()

    def _notify_speaking(self, speaking: bool) -> None:
        callback = self._on_speaking_changed
        if callback is not None:
            callback(bool(speaking))

    def _notify_error(self, error: Exception) -> None:
        callback = self._on_error
        if callback is not None:
            callback(error)
