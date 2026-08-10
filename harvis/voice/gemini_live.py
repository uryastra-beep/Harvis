from __future__ import annotations

import asyncio
import math
import os
import sys
import threading
import time
from array import array
from collections import deque
from collections.abc import Callable
from typing import Any

MODEL_NAME = "gemini-3.1-flash-live-preview"
INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000
AUDIO_CHANNELS = 1
INPUT_BLOCK_FRAMES = 800
INPUT_QUEUE_LIMIT = 8
TEXT_QUEUE_LIMIT = 12
SPECTRUM_BINS = 42
SPECTRUM_ANALYSIS_SAMPLES = 512

ToolExecutor = Callable[[str, dict[str, Any]], Any]
TextCallback = Callable[[str], None]
StatusCallback = Callable[[str], None]
ErrorCallback = Callable[[Exception], None]
AudioLevelCallback = Callable[[float], None]
SpectrumCallback = Callable[[list[float] | None], None]


class GeminiLiveError(RuntimeError):
    """Raised when the Gemini Live voice runtime cannot start or continue."""


class GeminiLiveVoice:
    """Stream voice or silent text commands through Gemini Live."""

    def __init__(
        self,
        *,
        language_tag: str = "es-419",
        voice_volume: int = 70,
        silent_mode: bool = False,
        execute_tool: ToolExecutor,
        on_input_transcript: TextCallback | None = None,
        on_output_transcript: TextCallback | None = None,
        on_audio_level: AudioLevelCallback | None = None,
        on_spectrum: SpectrumCallback | None = None,
        on_ready: Callable[[], None] | None = None,
        on_status: StatusCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> None:
        self._language_tag = language_tag
        self._voice_volume = max(0, min(100, int(voice_volume)))
        self._silent_mode = bool(silent_mode)
        self._microphone_muted = False
        self._execute_tool = execute_tool
        self._on_input_transcript = on_input_transcript
        self._on_output_transcript = on_output_transcript
        self._on_audio_level = on_audio_level
        self._on_spectrum = on_spectrum
        self._on_ready = on_ready
        self._on_status = on_status
        self._on_error = on_error

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._input_queue: asyncio.Queue[bytes] | None = None
        self._text_queue: asyncio.Queue[str] | None = None
        self._pending_text_commands: deque[str] = deque(maxlen=TEXT_QUEUE_LIMIT)
        self._input_stream: Any | None = None
        self._output_stream: Any | None = None
        self._sender_task: asyncio.Task | None = None
        self._text_sender_task: asyncio.Task | None = None
        self._receiver_task: asyncio.Task | None = None
        self._mute_input_until = 0.0
        self._state_lock = threading.Lock()

    @property
    def language_tag(self) -> str:
        return self._language_tag

    @property
    def silent_mode(self) -> bool:
        with self._state_lock:
            return self._silent_mode

    @property
    def microphone_muted(self) -> bool:
        with self._state_lock:
            return self._microphone_muted

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
        self._emit_silence()
        self._abort_audio_streams()

        loop = self._loop
        if loop is not None and loop.is_running():
            try:
                loop.call_soon_threadsafe(self._cancel_runtime_tasks)
            except RuntimeError:
                pass

        thread = self._thread
        if thread is None or thread is threading.current_thread():
            return

        if thread.is_alive():
            thread.join(timeout=3.0)

        if thread.is_alive():
            self._notify_status("Gemini Live is still stopping")
            return

        if self._thread is thread:
            self._thread = None

    def set_volume(self, volume: int) -> None:
        with self._state_lock:
            self._voice_volume = max(0, min(100, int(volume)))

    def set_silent_mode(self, enabled: bool) -> None:
        with self._state_lock:
            self._silent_mode = bool(enabled)

    def set_microphone_muted(self, muted: bool) -> bool:
        """Mute or unmute microphone forwarding without disconnecting Gemini Live."""

        normalized = bool(muted)
        with self._state_lock:
            self._microphone_muted = normalized

        if normalized:
            loop = self._loop
            if loop is not None and loop.is_running():
                try:
                    loop.call_soon_threadsafe(self._discard_queued_microphone_audio)
                except RuntimeError:
                    pass
            else:
                self._discard_queued_microphone_audio()

        return normalized

    def toggle_microphone_muted(self) -> bool:
        """Toggle microphone forwarding and return the new muted state."""

        with self._state_lock:
            target = not self._microphone_muted
        return self.set_microphone_muted(target)

    def set_language(self, language_tag: str) -> None:
        if language_tag == self._language_tag:
            return

        was_running = self.is_running
        if was_running:
            self.stop()

        self._language_tag = language_tag

        if was_running and not self.is_running:
            self.start()

    def send_text(self, text: str) -> bool:
        """Queue a text command for the active Gemini Live session."""

        value = " ".join(str(text).split()).strip()
        if not value:
            return False

        loop = self._loop
        text_queue = self._text_queue
        if loop is not None and loop.is_running() and text_queue is not None:
            try:
                loop.call_soon_threadsafe(self._queue_text_command, value)
                return True
            except RuntimeError:
                pass

        with self._state_lock:
            self._pending_text_commands.append(value)
        return True

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._run())
        except Exception as exc:
            self._emit_silence()
            self._notify_error(exc)
        finally:
            current_thread = threading.current_thread()
            if self._thread is current_thread:
                self._thread = None

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
        self._text_queue = asyncio.Queue(maxsize=TEXT_QUEUE_LIMIT)
        self._drain_pending_text_commands()

        input_stream = None
        output_stream = None
        silent_session = self.silent_mode

        try:
            if not silent_session:
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
                self._input_stream = input_stream
                self._output_stream = output_stream

            client = genai.Client(api_key=api_key)
            config = {
                "response_modalities": ["AUDIO"],
                "input_audio_transcription": {},
                "output_audio_transcription": {},
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": "Iapetus",
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

            async with client.aio.live.connect(
                model=MODEL_NAME,
                config=config,
            ) as session:
                if input_stream is not None:
                    input_stream.start()
                if output_stream is not None:
                    output_stream.start()

                sender = None
                if not silent_session:
                    sender = asyncio.create_task(
                        self._send_microphone_audio(session, types),
                        name="HarvisGeminiAudioSender",
                    )

                text_sender = asyncio.create_task(
                    self._send_text_commands(session),
                    name="HarvisGeminiTextSender",
                )
                receiver = asyncio.create_task(
                    self._receive_live_messages(session, types, output_stream),
                    name="HarvisGeminiReceiver",
                )
                self._sender_task = sender
                self._text_sender_task = text_sender
                self._receiver_task = receiver

                self._notify_status("Gemini Live ready")
                callback = self._on_ready
                if callback is not None:
                    callback()

                try:
                    while not self._stop_event.is_set():
                        if sender is not None and sender.done():
                            await sender
                            if not self._stop_event.is_set():
                                raise GeminiLiveError(
                                    "Gemini Live microphone sender stopped unexpectedly."
                                )

                        if text_sender.done():
                            await text_sender
                            if not self._stop_event.is_set():
                                raise GeminiLiveError(
                                    "Gemini Live text sender stopped unexpectedly."
                                )

                        if receiver.done():
                            await receiver
                            if not self._stop_event.is_set():
                                raise GeminiLiveError(
                                    "Gemini Live receiver stopped unexpectedly."
                                )

                        await asyncio.sleep(0.05)
                finally:
                    tasks = [task for task in (sender, text_sender, receiver) if task is not None]
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    self._sender_task = None
                    self._text_sender_task = None
                    self._receiver_task = None
        finally:
            self._emit_silence()
            self._abort_audio_streams()

            for stream in (input_stream, output_stream):
                if stream is None:
                    continue
                try:
                    stream.close()
                except Exception:
                    pass

            self._input_stream = None
            self._output_stream = None
            self._input_queue = None
            self._text_queue = None
            self._sender_task = None
            self._text_sender_task = None
            self._receiver_task = None
            self._loop = None

    def _drain_pending_text_commands(self) -> None:
        text_queue = self._text_queue
        if text_queue is None:
            return

        with self._state_lock:
            pending = list(self._pending_text_commands)
            self._pending_text_commands.clear()

        for value in pending:
            self._queue_text_command(value)

    def _abort_audio_streams(self) -> None:
        for stream in (self._input_stream, self._output_stream):
            if stream is None:
                continue
            try:
                stream.abort()
            except Exception:
                pass

    def _cancel_runtime_tasks(self) -> None:
        for task in (
            self._sender_task,
            self._text_sender_task,
            self._receiver_task,
        ):
            if task is not None and not task.done():
                task.cancel()

    def _discard_queued_microphone_audio(self) -> None:
        audio_queue = self._input_queue
        if audio_queue is None:
            return

        while True:
            try:
                audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def _audio_input_callback(self, indata, frames, time_info, status) -> None:
        if self._stop_event.is_set() or self.silent_mode or self.microphone_muted:
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

    def _queue_text_command(self, text: str) -> None:
        text_queue = self._text_queue
        if text_queue is None:
            with self._state_lock:
                self._pending_text_commands.append(text)
            return

        if text_queue.full():
            try:
                text_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

        try:
            text_queue.put_nowait(text)
        except asyncio.QueueFull:
            pass

    async def _send_microphone_audio(self, session, types) -> None:
        audio_queue = self._input_queue
        if audio_queue is None:
            return

        while not self._stop_event.is_set():
            try:
                chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.20)
            except TimeoutError:
                continue

            if self.microphone_muted:
                continue

            await session.send_realtime_input(
                audio=types.Blob(
                    data=chunk,
                    mime_type=f"audio/pcm;rate={INPUT_SAMPLE_RATE}",
                )
            )

    async def _send_text_commands(self, session) -> None:
        text_queue = self._text_queue
        if text_queue is None:
            return

        while not self._stop_event.is_set():
            try:
                text = await asyncio.wait_for(text_queue.get(), timeout=0.20)
            except TimeoutError:
                continue

            await session.send_realtime_input(text=text)

    async def _receive_live_messages(self, session, types, output_stream) -> None:
        while not self._stop_event.is_set():
            received_message = False

            async for response in session.receive():
                received_message = True

                if self._stop_event.is_set():
                    return

                await self._handle_live_response(
                    session,
                    types,
                    output_stream,
                    response,
                )

            self._emit_silence()

            # session.receive() completes at the end of a server turn.
            # Start a new receive iterator so later user turns keep working.
            if not received_message:
                await asyncio.sleep(0.01)

    async def _handle_live_response(
        self,
        session,
        types,
        output_stream,
        response,
    ) -> None:
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
        if self.silent_mode or output_stream is None:
            self._emit_silence()
            await asyncio.sleep(0)
            return

        self._mute_input_until = time.monotonic() + 0.35
        level, spectrum = self._analyze_pcm16(audio_data)
        self._emit_audio_analysis(level, spectrum)
        scaled_audio = self._scale_pcm16(audio_data)
        output_stream.write(scaled_audio)
        self._mute_input_until = time.monotonic() + 0.25
        await asyncio.sleep(0)

    @staticmethod
    def _analyze_pcm16(audio_data: bytes) -> tuple[float, list[float]]:
        usable_length = len(audio_data) - (len(audio_data) % 2)
        if usable_length <= 0:
            return 0.0, [0.0 for _ in range(SPECTRUM_BINS)]

        samples = array("h")
        samples.frombytes(audio_data[:usable_length])

        if sys.byteorder != "little":
            samples.byteswap()

        if not samples:
            return 0.0, [0.0 for _ in range(SPECTRUM_BINS)]

        mean_square = sum(float(sample) * float(sample) for sample in samples) / len(samples)
        raw_rms = math.sqrt(mean_square) / 32768.0
        level = max(0.0, min(1.0, (raw_rms - 0.0025) * 6.2))

        if level <= 0.003:
            return 0.0, [0.0 for _ in range(SPECTRUM_BINS)]

        if len(samples) > SPECTRUM_ANALYSIS_SAMPLES:
            start_index = max(
                0,
                (len(samples) - SPECTRUM_ANALYSIS_SAMPLES) // 2,
            )
            analysis_samples = samples[
                start_index : start_index + SPECTRUM_ANALYSIS_SAMPLES
            ]
        else:
            analysis_samples = samples

        sample_count = len(analysis_samples)
        if sample_count < 8:
            return level, [level for _ in range(SPECTRUM_BINS)]

        highest_frequency = min(8000.0, OUTPUT_SAMPLE_RATE * 0.45)
        lowest_frequency = 90.0
        frequency_ratio = highest_frequency / lowest_frequency

        windowed_samples = []
        denominator = max(1, sample_count - 1)
        for index, sample in enumerate(analysis_samples):
            window = 0.5 - 0.5 * math.cos(math.tau * index / denominator)
            windowed_samples.append((sample / 32768.0) * window)

        magnitudes: list[float] = []
        for bin_index in range(SPECTRUM_BINS):
            position = bin_index / max(1, SPECTRUM_BINS - 1)
            frequency = lowest_frequency * (frequency_ratio ** position)
            omega = math.tau * frequency / OUTPUT_SAMPLE_RATE
            coefficient = 2.0 * math.cos(omega)
            previous = 0.0
            previous_two = 0.0

            for sample in windowed_samples:
                current = sample + coefficient * previous - previous_two
                previous_two = previous
                previous = current

            power = (
                previous_two * previous_two
                + previous * previous
                - coefficient * previous * previous_two
            )
            magnitudes.append(math.sqrt(max(0.0, power)) / sample_count)

        peak = max(magnitudes, default=0.0)
        if peak <= 1e-9:
            return level, [0.0 for _ in range(SPECTRUM_BINS)]

        amplitude_envelope = min(1.0, 0.10 + level * 1.55)
        spectrum = [
            min(1.0, ((magnitude / peak) ** 0.58) * amplitude_envelope)
            for magnitude in magnitudes
        ]
        return level, spectrum

    def _emit_audio_analysis(self, level: float, spectrum: list[float]) -> None:
        level_callback = self._on_audio_level
        if level_callback is not None:
            level_callback(level)

        spectrum_callback = self._on_spectrum
        if spectrum_callback is not None:
            spectrum_callback(spectrum)

    def _emit_silence(self) -> None:
        level_callback = self._on_audio_level
        if level_callback is not None:
            level_callback(0.0)

        spectrum_callback = self._on_spectrum
        if spectrum_callback is not None:
            spectrum_callback(None)

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

        mode_instruction = (
            "Silent mode is active. Commands may arrive as typed text and should be treated as directly addressed "
            "to Harvis. Keep replies especially short because they are displayed in a compact popup."
            if self.silent_mode
            else "Speaking mode is active. Commands normally arrive by voice."
        )

        return (
            "You are Harvis, a concise desktop voice assistant. "
            "Only respond or use computer-control tools when the user clearly addresses you "
            "as Harvis or Jarvis, except typed commands sent through Silent mode, which are already addressed to you. "
            f"{language_instruction} {mode_instruction} "
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
