from __future__ import annotations

import platform
import shutil
import subprocess
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
    system_name = platform.system()

    if system_name == "Windows":
        _set_windows_master_volume(target)
        return

    if system_name == "Linux":
        _set_linux_master_volume(target)
        return

    raise SystemActionError(
        f"Master volume control is not supported on {system_name or 'this platform'} yet."
    )


def _set_windows_master_volume(target: int) -> None:
    try:
        from comtypes import CoInitialize, CoUninitialize
        from pycaw.pycaw import AudioUtilities

        CoInitialize()
        try:
            speakers = AudioUtilities.GetSpeakers()
            endpoint = speakers.EndpointVolume
            endpoint.SetMasterVolumeLevelScalar(target / 100.0, None)
        finally:
            CoUninitialize()
    except Exception as exc:
        raise SystemActionError("The Windows master volume could not be changed.") from exc


def _set_linux_master_volume(target: int) -> None:
    wpctl = shutil.which("wpctl")
    if wpctl:
        try:
            subprocess.run(
                [wpctl, "set-volume", "@DEFAULT_AUDIO_SINK@", f"{target / 100.0:.2f}"],
                check=True,
                capture_output=True,
                text=True,
            )
            return
        except subprocess.CalledProcessError:
            pass

    pactl = shutil.which("pactl")
    if pactl:
        try:
            subprocess.run(
                [pactl, "set-sink-volume", "@DEFAULT_SINK@", f"{target}%"],
                check=True,
                capture_output=True,
                text=True,
            )
            return
        except subprocess.CalledProcessError as exc:
            raise SystemActionError(
                "The Linux master volume could not be changed with pactl."
            ) from exc

    raise SystemActionError(
        "Linux volume control requires wpctl (PipeWire) or pactl (PulseAudio)."
    )
