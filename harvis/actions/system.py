from __future__ import annotations

import platform
import webbrowser


class SystemActionError(RuntimeError):
    """Raised when a requested system action cannot be completed."""


def open_default_browser(url: str) -> None:
    if not url.strip():
        raise ValueError("A URL is required.")

    if not webbrowser.open(url, new=2):
        raise SystemActionError("The default browser could not be opened.")


def set_master_volume(percent: int) -> None:
    target = max(0, min(100, int(percent)))

    if platform.system() != "Windows":
        raise SystemActionError("Master volume control is currently supported on Windows only.")

    try:
        from pycaw.pycaw import AudioUtilities

        speakers = AudioUtilities.GetSpeakers()
        endpoint = speakers.EndpointVolume
        endpoint.SetMasterVolumeLevelScalar(target / 100.0, None)
    except Exception as exc:
        raise SystemActionError("The master volume could not be changed.") from exc
