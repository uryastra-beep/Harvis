from __future__ import annotations

import contextlib
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from harvis.actions.system import SystemActionError
from harvis.assistant import HarvisAssistant, HarvisGeminiLiveVoice

REMOTE_AUDIO_BUFFER_MAX_BYTES = 24000 * 2 * 4
REMOTE_STATUS_MAX_CHARACTERS = 8192
SUPPORTED_REMOTE_AUDIO_OUTPUTS = {"pc", "phone", "both"}


class RemoteAudioHarvisGeminiLiveVoice(HarvisGeminiLiveVoice):
    """Harvis Gemini Live voice runtime with selectable PC and phone audio routing."""

    def __init__(
        self,
        *,
        on_remote_audio: Callable[[bytes], None],
        **kwargs: Any,
    ) -> None:
        self._remote_audio_lock = threading.RLock()
        self._remote_audio_output = "pc"
        self._on_remote_audio = on_remote_audio
        super().__init__(**kwargs)

    @property
    def audio_output_target(self) -> str:
        with self._remote_audio_lock:
            return self._remote_audio_output

    def set_audio_output_target(self, target: str) -> str:
        normalized = str(target).strip().casefold()
        if normalized not in SUPPORTED_REMOTE_AUDIO_OUTPUTS:
            raise ValueError("Audio output must be pc, phone, or both.")
        with self._remote_audio_lock:
            self._remote_audio_output = normalized
        return normalized

    async def _play_audio(self, output_stream, audio_data: bytes) -> None:
        if self.silent_mode:
            self._emit_silence()
            await self._yield_audio_loop()
            return

        self._mute_input_until = time.monotonic() + 0.35
        level, spectrum = self._analyze_pcm16(audio_data)
        self._emit_audio_analysis(level, spectrum)
        scaled_audio = self._scale_pcm16(audio_data)
        target = self.audio_output_target

        if target in {"phone", "both"}:
            with contextlib.suppress(Exception):
                self._on_remote_audio(scaled_audio)

        if target in {"pc", "both"} and output_stream is not None:
            output_stream.write(scaled_audio)

        self._mute_input_until = time.monotonic() + 0.25
        await self._yield_audio_loop()

    @staticmethod
    async def _yield_audio_loop() -> None:
        import asyncio

        await asyncio.sleep(0)


class RemoteCapableHarvisAssistant(HarvisAssistant):
    """Expose a small thread-safe bridge for paired mobile remote control."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._remote_state_lock = threading.RLock()
        self._remote_last_status = "Assistant not started"
        self._remote_last_response = ""
        self._remote_audio_chunks: deque[bytes] = deque()
        self._remote_audio_buffer_bytes = 0
        super().__init__(*args, **kwargs)

        settings = self._settings
        self._voice = RemoteAudioHarvisGeminiLiveVoice(
            on_remote_audio=self._capture_remote_audio,
            user_name=settings.user_name,
            language_tag=settings.speech_language,
            voice_volume=settings.voice_volume,
            silent_mode=settings.assistant_mode == "Silent",
            execute_tool=self._execute_tool,
            on_input_transcript=self._handle_input_transcript,
            on_output_transcript=self._handle_output_transcript,
            on_audio_level=self._handle_audio_level,
            on_spectrum=self._handle_spectrum,
            on_ready=self._handle_live_ready,
            on_status=self._notify_status,
            on_error=self._handle_live_error,
        )

    def send_remote_command(self, text: str) -> None:
        """Queue a mobile text command in either Speaking or Silent mode."""

        command = " ".join(str(text).split()).strip()
        if not command:
            raise ValueError("Remote command cannot be empty.")

        self.ensure_active_session()
        self._record_visual_confirmation_response(command, complete_input=True)
        self._set_watermark_context(command)
        if not self._voice.send_text(command):
            raise SystemActionError("Harvis could not queue the remote command.")
        self._notify_status("Remote command sent")

    def set_remote_audio_output(self, target: str) -> str:
        """Route Harvis voice audio to the computer, paired phone, or both."""

        normalized = self._voice.set_audio_output_target(target)
        if normalized == "pc":
            self._clear_remote_audio()
        self._notify_status(
            {
                "pc": "Audio output: computer",
                "phone": "Audio output: phone",
                "both": "Audio output: phone and computer",
            }[normalized]
        )
        return normalized

    def take_remote_audio(self) -> bytes:
        """Drain buffered 24 kHz mono PCM16 audio for the paired mobile client."""

        with self._remote_state_lock:
            if not self._remote_audio_chunks:
                return b""
            payload = b"".join(self._remote_audio_chunks)
            self._remote_audio_chunks.clear()
            self._remote_audio_buffer_bytes = 0
        return payload

    def remote_status(self) -> dict[str, Any]:
        """Return the minimal state exposed to an authenticated mobile client."""

        with self._remote_state_lock:
            status = self._remote_last_status
            response = self._remote_last_response

        return {
            "status": status,
            "response": response,
            "mode": self._settings.assistant_mode,
            "microphone_muted": self.microphone_muted,
            "assistant_running": self._voice.is_running,
            "audio_output": self._voice.audio_output_target,
        }

    def _capture_remote_audio(self, audio_data: bytes) -> None:
        chunk = bytes(audio_data)
        if not chunk:
            return

        if len(chunk) > REMOTE_AUDIO_BUFFER_MAX_BYTES:
            chunk = chunk[-REMOTE_AUDIO_BUFFER_MAX_BYTES:]

        with self._remote_state_lock:
            self._remote_audio_chunks.append(chunk)
            self._remote_audio_buffer_bytes += len(chunk)
            while (
                self._remote_audio_chunks
                and self._remote_audio_buffer_bytes > REMOTE_AUDIO_BUFFER_MAX_BYTES
            ):
                removed = self._remote_audio_chunks.popleft()
                self._remote_audio_buffer_bytes -= len(removed)

    def _clear_remote_audio(self) -> None:
        with self._remote_state_lock:
            self._remote_audio_chunks.clear()
            self._remote_audio_buffer_bytes = 0

    def _handle_output_transcript(self, text: str) -> None:
        with self._remote_state_lock:
            self._remote_last_response = str(text)[-REMOTE_STATUS_MAX_CHARACTERS:]
        super()._handle_output_transcript(text)

    def _notify_status(self, status: str) -> None:
        with self._remote_state_lock:
            self._remote_last_status = str(status)[-REMOTE_STATUS_MAX_CHARACTERS:]
        super()._notify_status(status)


__all__ = [
    "REMOTE_AUDIO_BUFFER_MAX_BYTES",
    "REMOTE_STATUS_MAX_CHARACTERS",
    "SUPPORTED_REMOTE_AUDIO_OUTPUTS",
    "RemoteAudioHarvisGeminiLiveVoice",
    "RemoteCapableHarvisAssistant",
]
