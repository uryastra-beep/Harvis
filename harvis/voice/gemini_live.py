from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
from array import array
from collections.abc import Callable
from typing import Any

MODEL_NAME = "gemini-3.1-flash-live-preview"
INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000
AUDIO_CHANNELS = 1
INPUT_BLOCK_FRAMES = 1600
INPUT_QUEUE_LIMIT = 20

ToolExecutor = Callable[[str, dict[str, Any]], Any]
TextCallback = Callable[[str], None]
StatusCallback = Callable[[str], None]
ErrorCallback = Callable[[Exception], None]


class GeminiLiveError(RuntimeError):
    """Raised when the Gemini Live voice runtime cannot start or continue."""


class GeminiLiveVoice:
    """Stream microphone audio to Gemini Live and play native audio responses."""

    def __init__(
        self,
        *,
        language_tag: str = "es-419",
        voice_volume: int = 70,
        execute_tool: ToolExecutor,
        on_input_transcript: TextCallback | None = None,
        on_output_transcript: TextCallback | None = None,
        on_ready: Callable[[], None] | None = None,
        on_status: StatusCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> None:
        self._language_tag = language_tag
        self._voice_volume = max(0, min(100, int(voice_volume)))
        self._execute_tool = execute_tool
        self._on_input_transcript = on_input_transcript
        self._on_output_transcript = on_output_transcript
        self._on_ready = on_ready
        self._on_status = on_status
        self._on_error = on_error

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._input_queue: asyncio.Queue[bytes] | None = None
        self._mute_input_until = 0.0
        self._state_lock = threading.Lock()

    @property
    def language_tag(self) -> str:
        return self._language_tag

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._thread_main,
            name="HarvisGeminiLive",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(lambda: None)

        thread = self._thread
        if (
            thread is not None
            and thread is not threading.current_thread()
            and thread.is_alive()
        ):
            thread.join(timeout=3.0)

        self._thread = None

    def set_volume(self, volume: int) -> None:
        with self._state_lock:
            self._voice_volume = max(0, min(100, int(volume)))

    def set_language(self, language_tag: str) -> None:
        if language_tag == self._language_tag:
            return

        was_running = self.is_running
        if was_running:
            self.stop()

        self._language_tag = language_tag

        if was_running:
            self.start()

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._run())
        except Exception as exc:
            self._notify_error(exc)

    async def _run(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise GeminiLiveError(
                "GEMINI_API_KEY is not configured. Set it before starting Harvis."
            )

        try:
            import sounddevice as sd
        except ImportError as exc:
            raise GeminiLiveError(
                "The sounddevice package is not installed. "
                "Run: python -m pip install -r requirements.txt"
            ) from exc

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise GeminiLiveError(
                "The google-genai package is not installed. "
                "Run: python -m pip install -r requirements.txt"
            ) from exc

        self._loop = asyncio.get_running_loop()
        self._input_queue = asyncio.Queue(maxsize=INPUT_QUEUE_LIMIT)

        input_stream = sd.RawInputStream(
            samplerate=INPUT_SAMPLE_RATE,
            blocksize=INPUT_BLOCK_FRAMES,
            channels=AUDIO_CHANNELS,
            dtype="int16",
            callback=self._audio_input_callback,
        )
        output_stream = sd.RawOutputStream(
            samplerate=OUTPUT_SAMPLE_RATE,
            channels=AUDIO_CHANNELS,
            dtype="int16",
        )

        client = genai.Client(api_key=api_key)
        config = {
            "response_modalities": ["AUDIO"],
            "input_audio_transcription": {},
            "output_audio_transcription": {},
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": "Kore",
                    }
                }
            },
            "thinking_config": {
                "thinking_level": "minimal",
            },
            "system_instruction": self._system_instruction(),
            "tools": self._tool_declarations(),
        }

        self._notify_status("Connecting to Gemini Live")

        try:
            async with client.aio.live.connect(
                model=MODEL_NAME,
                config=config,
            ) as session:
                input_stream.start()
                output_stream.start()
                self._notify_status("Gemini Live connected")

                callback = self._on_ready
                if callback is not None:
                    callback()

                sender = asyncio.create_task(
                    self._send_microphone_audio(session, types),
                    name="HarvisGeminiAudioSender",
                )
                receiver = asyncio.create_task(
                    self._receive_live_messages(session, types, output_stream),
                    name="HarvisGeminiReceiver",
                )

                try:
                    while not self._stop_event.is_set():
                        if sender.done():
                            await sender
                        if receiver.done():
                            await receiver
                        await asyncio.sleep(0.05)
                finally:
                    sender.cancel()
                    receiver.cancel()
                    await asyncio.gather(sender, receiver, return_exceptions=True)
        finally:
            try:
                input_stream.stop()
            except Exception:
                pass
            try:
                output_stream.stop()
            except Exception:
                pass
            input_stream.close()
            output_stream.close()
            self._input_queue = None
            self._loop = None

    def _audio_input_callback(self, indata, frames, time_info, status) -> None:
        if self._stop_event.is_set():
            return

        if status:
            self._notify_status(f"Microphone status: {status}")

        if time.monotonic() < self._mute_input_until:
            return

        loop = self._loop
        audio_queue = self._input_queue
        if loop is None or audio_queue is None:
            return

        chunk = bytes(indata)
        loop.call_soon_threadsafe(self._queue_audio_chunk, chunk)

    def _queue_audio_chunk(self, chunk: bytes) -> None:
        audio_queue = self._input_queue
        if audio_queue is None:
            return

        if audio_queue.full():
            try:
                audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

        try:
            audio_queue.put_nowait(chunk)
        except asyncio.QueueFull:
            pass

    async def _send_microphone_audio(self, session, types) -> None:
        audio_queue = self._input_queue
        if audio_queue is None:
            return

        while not self._stop_event.is_set():
            try:
                chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.25)
            except TimeoutError:
                continue

            await session.send_realtime_input(
                audio=types.Blob(
                    data=chunk,
                    mime_type=f"audio/pcm;rate={INPUT_SAMPLE_RATE}",
                )
            )

    async def _receive_live_messages(self, session, types, output_stream) -> None:
        async for response in session.receive():
            if self._stop_event.is_set():
                return

            server_content = response.server_content
            if server_content is not None:
                input_transcription = server_content.input_transcription
                if input_transcription and input_transcription.text:
                    callback = self._on_input_transcript
                    if callback is not None:
                        callback(input_transcription.text.strip())

                output_transcription = server_content.output_transcription
                if output_transcription and output_transcription.text:
                    callback = self._on_output_transcript
                    if callback is not None:
                        callback(output_transcription.text.strip())

            if response.tool_call is not None:
                await self._handle_tool_calls(session, types, response.tool_call)

            audio_data = response.data
            if audio_data:
                await self._play_audio(output_stream, audio_data)

    async def _handle_tool_calls(self, session, types, tool_call) -> None:
        function_responses = []

        for function_call in tool_call.function_calls:
            arguments = dict(function_call.args or {})
            try:
                result = self._execute_tool(function_call.name, arguments)
                if result is None:
                    result = {"ok": True}
                response_body = {"ok": True, "result": result}
            except Exception as exc:
                response_body = {
                    "ok": False,
                    "error": str(exc),
                }

            function_responses.append(
                types.FunctionResponse(
                    id=function_call.id,
                    name=function_call.name,
                    response=response_body,
                )
            )

        if function_responses:
            await session.send_tool_response(
                function_responses=function_responses,
            )

    async def _play_audio(self, output_stream, audio_data: bytes) -> None:
        self._mute_input_until = time.monotonic() + 0.35
        scaled_audio = self._scale_pcm16(audio_data)
        await asyncio.to_thread(output_stream.write, scaled_audio)
        self._mute_input_until = time.monotonic() + 0.25

    def _scale_pcm16(self, audio_data: bytes) -> bytes:
        with self._state_lock:
            volume = self._voice_volume

        if volume >= 100:
            return audio_data
        if volume <= 0:
            return bytes(len(audio_data))

        samples = array("h")
        samples.frombytes(audio_data)

        if sys.byteorder != "little":
            samples.byteswap()

        scale = volume / 100.0
        for index, sample in enumerate(samples):
            value = int(sample * scale)
            samples[index] = max(-32768, min(32767, value))

        if sys.byteorder != "little":
            samples.byteswap()

        return samples.tobytes()

    def _system_instruction(self) -> str:
        if self._language_tag == "es-419":
            language_instruction = (
                "Reply in natural Latin American Spanish by default. "
                "Understand English too, and follow the user's language when they explicitly switch."
            )
        else:
            language_instruction = (
                "Reply in natural US English by default. "
                "Understand Spanish too, and follow the user's language when they explicitly switch."
            )

        return (
            "You are Harvis, a concise desktop voice assistant. "
            "Only respond or use computer-control tools when the user clearly addresses you "
            "as Harvis or Jarvis. "
            f"{language_instruction} "
            "Keep spoken responses short unless the user asks for detail. "
            "Use tools for computer actions instead of claiming you performed an action yourself. "
            "Never claim a computer action succeeded until the tool response confirms it."
        )

    @staticmethod
    def _tool_declarations() -> list[dict[str, Any]]:
        return [
            {
                "function_declarations": [
                    {
                        "name": "set_master_volume",
                        "description": (
                            "Set the computer's master output volume to a percentage from 0 to 100."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "percent": {
                                    "type": "integer",
                                    "description": "Target master volume percentage from 0 to 100.",
                                }
                            },
                            "required": ["percent"],
                        },
                    },
                    {
                        "name": "open_url",
                        "description": (
                            "Open a complete HTTP or HTTPS URL in the user's default web browser."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "url": {
                                    "type": "string",
                                    "description": (
                                        "Complete URL beginning with http:// or https://."
                                    ),
                                }
                            },
                            "required": ["url"],
                        },
                    },
                ]
            }
        ]

    def _notify_status(self, status: str) -> None:
        callback = self._on_status
        if callback is not None:
            callback(status)

    def _notify_error(self, error: Exception) -> None:
        callback = self._on_error
        if callback is not None:
            callback(error)
