from __future__ import annotations

import threading
from collections.abc import Callable

from comtypes import CoInitialize, CoUninitialize
from comtypes.client import CreateObject, GetEvents, PumpEvents


class _RecognitionSink:
    def __init__(
        self,
        on_text: Callable[[str], None],
        should_ignore: Callable[[], bool] | None,
    ) -> None:
        self._on_text = on_text
        self._should_ignore = should_ignore

    def Recognition(self, *args) -> None:
        self._handle_recognition(args)

    def _ISpeechRecoContextEvents_Recognition(self, *args) -> None:
        self._handle_recognition(args)

    def _handle_recognition(self, args: tuple[object, ...]) -> None:
        if self._should_ignore is not None and self._should_ignore():
            return

        if not args:
            return

        result = args[-1]
        try:
            text = str(result.PhraseInfo.GetText()).strip()
        except Exception:
            return

        if text:
            self._on_text(text)


class SapiSpeechListener:
    """Continuously transcribe the default Windows microphone through SAPI."""

    SGDS_INACTIVE = 0
    SGDS_ACTIVE = 1

    def __init__(
        self,
        on_text: Callable[[str], None],
        *,
        should_ignore: Callable[[], bool] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._on_text = on_text
        self._should_ignore = should_ignore
        self._on_error = on_error

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker,
            name="HarvisSapiListener",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)

        self._thread = None

    def _worker(self) -> None:
        CoInitialize()
        recognition_context = None
        grammar = None
        connection = None

        try:
            recognition_context = CreateObject("SAPI.SpSharedRecoContext")
            grammar = recognition_context.CreateGrammar(0)

            try:
                grammar.DictationLoad("", 0)
            except Exception:
                pass

            sink = _RecognitionSink(
                on_text=self._on_text,
                should_ignore=self._should_ignore,
            )
            connection = GetEvents(recognition_context, sink)
            grammar.DictationSetState(self.SGDS_ACTIVE)

            while not self._stop_event.is_set():
                PumpEvents(0.05)
        except Exception as exc:
            callback = self._on_error
            if callback is not None:
                callback(exc)
        finally:
            if grammar is not None:
                try:
                    grammar.DictationSetState(self.SGDS_INACTIVE)
                except Exception:
                    pass

            if connection is not None:
                try:
                    connection.disconnect()
                except Exception:
                    pass

            connection = None
            grammar = None
            recognition_context = None
            CoUninitialize()
