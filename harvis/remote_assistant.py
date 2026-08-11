from __future__ import annotations

import threading
from typing import Any

from harvis.actions.system import SystemActionError
from harvis.assistant import HarvisAssistant


class RemoteCapableHarvisAssistant(HarvisAssistant):
    """Expose a small thread-safe bridge for paired mobile remote control."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._remote_state_lock = threading.RLock()
        self._remote_last_status = "Assistant not started"
        self._remote_last_response = ""
        super().__init__(*args, **kwargs)

    def send_remote_command(self, text: str) -> None:
        """Queue a mobile text command in either Speaking or Silent mode."""

        command = " ".join(str(text).split()).strip()
        if not command:
            raise ValueError("Remote command cannot be empty.")

        self._set_watermark_context(command)
        if not self._voice.send_text(command):
            raise SystemActionError("Harvis could not queue the remote command.")
        self._notify_status("Remote command sent")

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
        }

    def _handle_output_transcript(self, text: str) -> None:
        with self._remote_state_lock:
            self._remote_last_response = str(text)
        super()._handle_output_transcript(text)

    def _notify_status(self, status: str) -> None:
        with self._remote_state_lock:
            self._remote_last_status = str(status)
        super()._notify_status(status)


__all__ = ["RemoteCapableHarvisAssistant"]
