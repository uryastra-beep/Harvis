from __future__ import annotations

import threading
from collections.abc import Callable

from comtypes import CoInitialize, CoUninitialize
from comtypes.client import CreateObject, GetEvents, PumpEvents


SAPI_LANGUAGE_IDS = {
    "es-419": "580A",
    "en-US": "409",
}


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

    def FalseRecognition(self, *args) -> None:
        return

    def _ISpeechRecoContextEvents_FalseRecognition(self, *args) -> None:
        return

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
        language_tag: str = "es-419",
        should_ignore: Callable[[], bool] | None = None,
        on_ready: Callable[[], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._on_text = on_text
        self._language_tag = language_tag
        self._should_ignore = should_ignore
        self._on_ready = on_ready
        self._on_error = on_error

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._ready_event = threading.Event()

    @property
    def is_ready(self) -> bool:
        return self._ready_event.is_set()

    @property
    def language_tag(self) -> str:
        return self._language_tag

    def set_language(self, language_tag: str) -> None:
        if language_tag not in SAPI_LANGUAGE_IDS:
            raise ValueError(f"Unsupported speech language: {language_tag}")

        if language_tag == self._language_tag:
            return

        was_running = self._thread is not None and self._thread.is_alive()
        if was_running:
            self.stop()

        self._language_tag = language_tag

        if was_running:
            self.start()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._ready_event.clear()
        self._thread = threading.Thread(
            target=self._worker,
            name="HarvisSapiListener",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        thread = self._thread
        if self._thread is not threading.current_thread() and thread is not None and thread.is_alive():
            thread.join(timeout=1.5)

        self._thread = None
        self._ready_event.clear()

    def _worker(self) -> None:
        CoInitialize()
        recognizer = None
        recognition_context = None
        grammar = None
        connection = None

        try:
            sapi_language_id = SAPI_LANGUAGE_IDS.get(self._language_tag)
            if sapi_language_id is None:
                raise RuntimeError(
                    f"No SAPI language mapping exists for {self._language_tag}."
                )

            recognizer = CreateObject("SAPI.SpInprocRecognizer")
            recognizers = recognizer.GetRecognizers(
                f"Language={sapi_language_id}",
                "",
            )

            if recognizers.Count < 1:
                raise RuntimeError(
                    "No installed Windows SAPI speech recognizer supports "
                    f"{self._language_tag}."
                )

            recognizer.Recognizer = recognizers.Item(0)

            audio_inputs = recognizer.GetAudioInputs()
            if audio_inputs.Count < 1:
                raise RuntimeError("No Windows audio input device is available to SAPI.")
            recognizer.AudioInput = audio_inputs.Item(0)

            recognition_context = recognizer.CreateRecoContext()
            grammar = recognition_context.CreateGrammar(0)
            grammar.DictationLoad("", 0)

            sink = _RecognitionSink(
                on_text=self._on_text,
                should_ignore=self._should_ignore,
            )
            connection = GetEvents(recognition_context, sink)
            grammar.DictationSetState(self.SGDS_ACTIVE)

            self._ready_event.set()
            callback = self._on_ready
            if callback is not None:
                callback()

            while not self._stop_event.is_set():
                PumpEvents(0.05)
        except Exception as exc:
            self._ready_event.clear()
            callback = self._on_error
            if callback is not None:
                callback(exc)
        finally:
            self._ready_event.clear()

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
            recognizer = None
            CoUninitialize()
