from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from harvis import __version__

RELEASES_API_URL = "https://api.github.com/repos/uryastra-beep/Harvis/releases/latest"
RELEASES_PAGE_URL = "https://github.com/uryastra-beep/Harvis/releases"
UPDATE_TIMEOUT_SECONDS = 6.0
MAX_RELEASE_RESPONSE_BYTES = 1_000_000


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    available: bool
    release_url: str
    release_name: str


def check_for_updates() -> UpdateInfo:
    request = urllib.request.Request(
        RELEASES_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Harvis/{__version__}",
        },
    )
    try:
        # The URL is a fixed HTTPS GitHub API endpoint, never user-provided.
        with urllib.request.urlopen(  # nosec B310
            request,
            timeout=UPDATE_TIMEOUT_SECONDS,
        ) as response:
            body = response.read(MAX_RELEASE_RESPONSE_BYTES + 1)
            if len(body) > MAX_RELEASE_RESPONSE_BYTES:
                raise RuntimeError("GitHub returned an unexpectedly large update response.")
            payload = json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return UpdateInfo(
                current_version=__version__,
                latest_version=__version__,
                available=False,
                release_url=RELEASES_PAGE_URL,
                release_name="No published release",
            )
        raise RuntimeError(f"GitHub update check failed with HTTP {exc.code}.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Harvis could not check for updates: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("GitHub returned an invalid update response.")
    tag = str(payload.get("tag_name", "")).strip().removeprefix("v")
    release_url = str(payload.get("html_url", RELEASES_PAGE_URL)).strip()
    release_name = str(payload.get("name", tag or "Latest release")).strip()
    available = bool(tag and _version_tuple(tag) > _version_tuple(__version__))
    return UpdateInfo(
        current_version=__version__,
        latest_version=tag or __version__,
        available=available,
        release_url=release_url or RELEASES_PAGE_URL,
        release_name=release_name,
    )


def _version_tuple(version: str) -> tuple[int, int, int, int]:
    numbers = [int(value) for value in re.findall(r"\d+", str(version))[:4]]
    return tuple((numbers + [0, 0, 0, 0])[:4])


__all__ = [
    "RELEASES_API_URL",
    "RELEASES_PAGE_URL",
    "UpdateInfo",
    "check_for_updates",
]
