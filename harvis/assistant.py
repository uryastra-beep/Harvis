from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from harvis.actions.app_discovery import (
    close_discovered_application,
    open_discovered_application,
)
from harvis.actions.desktop import (
    close_application,
    control_browser,
    control_media,
    open_application,
)
from harvis.actions.screen_control import move_pointer, type_text, vision_click
from harvis.actions.system import SystemActionError
from harvis.config import HarvisSettings
from harvis.core.intents import Intent, IntentType
from harvis.core.router import IntentRouter
from harvis.voice.gemini_live import GeminiLiveVoice


class HarvisGeminiLiveVoice(GeminiLiveVoice):
    """Gemini Live runtime with Harvis desktop-control tools registered."""

    def _system_instruction(self) -> str:
        return (
            f"{super()._system_instruction()} "
            "You can operate the desktop through approved tools. Prefer direct local tools for "
            "opening applications, closing applications, browser shortcuts, media controls, and typing. "
            "Use vision_click only when the user explicitly asks you to visually find and click something "
            "that is currently visible on the screen. Before calling vision_click, briefly speak a natural "
            "filler phrase in the user's current language, such as 'Hmm, let me look for it.' After a "
            "successful visual click, briefly acknowledge that you found it, such as 'Ah, there it is.' "
            "If the requested element is hidden until the pointer reaches an edge, use move_pointer first, "
            "wait for that tool result, and then use vision_click on the newly visible UI. "
            "For example, to reveal an auto-hidden taskbar, move the pointer to bottom_center before looking "
            "for the requested taskbar icon. If vision_click reports confirmation_required, ask the user for "
            "explicit confirmation and do not call it again with confirmed=true until the user confirms. "
            "Never take a screen capture merely out of curiosity or when a direct local tool can complete the task."
        )

    @staticmethod
    def _tool_declarations() -> list[dict[str, Any]]:
        base_declarations = GeminiLiveVoice._tool_declarations()
        base_functions = list(base_declarations[0]["function_declarations"])

        desktop_functions = [
            {
                "name": "open_application",
                "description": (
                    "Open an installed desktop application by its normal human-readable name. "
                    "Harvis can use known launchers first and then dynamically search installed applications."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_name": {
                            "type": "string",
                            "description": (
                                "Application name, for example Chrome, Spotify, WhatsApp, OBS, Photoshop, "
                                "Discord, VS Code, Notepad, Calculator, Terminal, or another installed app."
                            ),
                        }
                    },
                    "required": ["app_name"],
                },
            },
            {
                "name": "close_application",
                "description": (
                    "Close an installed desktop application's visible window. "
                    "Use only when the user explicitly asks to close or quit the application."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_name": {
                            "type": "string",
                            "description": "Human-readable application name to close.",
                        }
                    },
                    "required": ["app_name"],
                },
            },
            {
                "name": "browser_control",
                "description": (
                    "Control the currently focused browser window. "
                    "Use this for common tab and navigation actions instead of screen vision."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "close_tab",
                                "new_tab",
                                "reopen_tab",
                                "refresh",
                                "back",
                                "forward",
                                "focus_address",
                            ],
                            "description": "Browser action to perform in the active browser window.",
                        }
                    },
                    "required": ["action"],
                },
            },
            {
                "name": "media_control",
                "description": (
                    "Control system media playback, including Spotify and other media applications."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "play_pause",
                                "next_track",
                                "previous_track",
                            ],
                            "description": "Media playback action to perform.",
                        }
                    },
                    "required": ["action"],
                },
            },
            {
                "name": "move_pointer",
                "description": (
                    "Move the mouse pointer to a screen edge or common position without clicking. "
                    "Use this to reveal hover-triggered or auto-hidden UI before a visual click."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "destination": {
                            "type": "string",
                            "enum": [
                                "top_left",
                                "top_center",
                                "top_right",
                                "center",
                                "bottom_left",
                                "bottom_center",
                                "bottom_right",
                                "left_center",
                                "right_center",
                            ],
                            "description": (
                                "Destination on the primary display. bottom_center is appropriate for "
                                "revealing an auto-hidden Windows taskbar."
                            ),
                        }
                    },
                    "required": ["destination"],
                },
            },
            {
                "name": "vision_click",
                "description": (
                    "Take a full-screen screenshot, use Gemini vision to find a user-described visible UI "
                    "element, move the pointer to it, and click it. Use only for explicit visual interaction "
                    "requests when a direct local control is not more appropriate."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": (
                                "Precise natural-language description of the visible UI target, including "
                                "text, icon identity, color, position, or nearby context when known."
                            ),
                        },
                        "button": {
                            "type": "string",
                            "enum": ["left", "right", "double_left"],
                            "description": "Mouse click type. Use left unless the user requests otherwise.",
                        },
                        "confirmed": {
                            "type": "boolean",
                            "description": (
                                "Set true only after the user explicitly confirms a consequential or destructive "
                                "visual action that previously returned confirmation_required."
                            ),
                        },
                    },
                    "required": ["target"],
                },
            },
            {
                "name": "type_text",
                "description": (
                    "Type or paste the exact requested text into the currently focused editable field. "
                    "Use after the correct text field or application has focus."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Exact text the user asked Harvis to enter.",
                        }
                    },
                    "required": ["text"],
                },
            },
        ]

        return [
            {
                "function_declarations": [
                    *base_functions,
                    *desktop_functions,
                ]
            }
        ]


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

        self._voice = HarvisGeminiLiveVoice(
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

        if name == "open_application":
            app_name = str(arguments.get("app_name", "")).strip()
            if not app_name:
                raise ValueError("open_application requires app_name.")

            try:
                open_application(app_name)
                result = {
                    "status": "completed",
                    "application": app_name,
                    "method": "known_launcher",
                }
            except SystemActionError:
                result = open_discovered_application(app_name)
            return result

        if name == "close_application":
            app_name = str(arguments.get("app_name", "")).strip()
            if not app_name:
                raise ValueError("close_application requires app_name.")

            try:
                close_application(app_name)
                result = {
                    "status": "completed",
                    "application": app_name,
                    "method": "known_launcher",
                }
            except SystemActionError:
                result = close_discovered_application(app_name)
            return result

        if name == "browser_control":
            action = str(arguments.get("action", "")).strip()
            if not action:
                raise ValueError("browser_control requires action.")

            control_browser(action)
            return {
                "status": "completed",
                "action": action,
            }

        if name == "media_control":
            action = str(arguments.get("action", "")).strip()
            if not action:
                raise ValueError("media_control requires action.")

            control_media(action)
            return {
                "status": "completed",
                "action": action,
            }

        if name == "move_pointer":
            destination = str(arguments.get("destination", "")).strip()
            if not destination:
                raise ValueError("move_pointer requires destination.")
            return move_pointer(destination)

        if name == "vision_click":
            target = str(arguments.get("target", "")).strip()
            if not target:
                raise ValueError("vision_click requires target.")

            self._notify_status(f"Looking for on-screen target: {target}")
            result = vision_click(
                target,
                button=str(arguments.get("button", "left")),
                confirmed=bool(arguments.get("confirmed", False)),
            )
            if result.get("status") == "clicked":
                self._notify_status(f"Clicked on-screen target: {target}")
            elif result.get("status") == "confirmation_required":
                self._notify_status(f"Confirmation required before clicking: {target}")
            else:
                self._notify_status(f"Could not confidently click: {target}")
            return result

        if name == "type_text":
            text = str(arguments.get("text", ""))
            return type_text(text)

        raise ValueError(f"Unsupported Harvis tool: {name}")

    def _notify_status(self, status: str) -> None:
        callback = self._on_status
        if callback is not None:
            callback(status)
