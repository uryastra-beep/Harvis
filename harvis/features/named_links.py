from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from harvis.actions.system import open_default_browser
from harvis.features.storage import atomic_write_text, harvis_data_dir

DEFAULT_LINKS = """# Harvis named links
# One link per line using: Name: https://example.com/
# Lines beginning with # are ignored.

Oxford: https://englishhub.oup.com/
Woot it: https://www.wootit.com/ghm/v4/home/
"""


def named_links_path() -> Path:
    path = harvis_data_dir() / "links.txt"
    if not path.exists():
        atomic_write_text(path, DEFAULT_LINKS)
    return path


def parse_named_links(path: Path | None = None) -> dict[str, tuple[str, str]]:
    source = path or named_links_path()
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"Harvis could not read named links: {exc}") from exc

    links: dict[str, tuple[str, str]] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([^:]{1,80}):\s*(https?://\S+)\s*$", line, re.IGNORECASE)
        if match is None:
            continue
        name = " ".join(match.group(1).split()).strip()
        url = match.group(2).strip().rstrip(">")
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            links[name.casefold()] = (name, url)
    return links


def open_named_link(name: str, *, path: Path | None = None) -> dict[str, Any]:
    requested = " ".join(str(name).split()).strip()
    if not requested:
        raise ValueError("A named link is required.")

    links = parse_named_links(path)
    match = links.get(requested.casefold())
    if match is None:
        return {
            "status": "not_found",
            "name": requested,
            "available_names": sorted(display for display, _ in links.values()),
            "links_file": str(path or named_links_path()),
        }

    display_name, url = match
    open_default_browser(url)
    return {
        "status": "completed",
        "name": display_name,
        "url": url,
    }
