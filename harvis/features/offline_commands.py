from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

ToolExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class OfflineCommand:
    action: str
    arguments: dict[str, Any]


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value))
    without_marks = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(
        re.sub(r"[^a-zA-Z0-9%:/._?=&+\-\s]", " ", without_marks)
        .casefold()
        .split()
    )


class OfflineCommandRouter:
    """Recognize a conservative set of deterministic commands without Gemini."""

    _SITE_URLS = {
        "google": "https://www.google.com/",
        "github": "https://github.com/",
        "gmail": "https://mail.google.com/",
        "youtube": "https://www.youtube.com/",
        "calendar": "https://calendar.google.com/",
        "calendario": "https://calendar.google.com/",
    }
    _MEDIA_ACTIONS = {
        "play": "play_pause",
        "pause": "play_pause",
        "pausa": "play_pause",
        "reproduce": "play_pause",
        "next song": "next_track",
        "next track": "next_track",
        "siguiente cancion": "next_track",
        "previous song": "previous_track",
        "previous track": "previous_track",
        "cancion anterior": "previous_track",
    }

    def parse(self, text: str) -> OfflineCommand | None:
        command = _normalize(text)
        command = re.sub(r"^(?:harvis|jarvis)\s+", "", command).strip()
        if not command:
            return None

        if command in {"apagate", "shutdown harvis", "exit harvis", "cierra harvis"}:
            return OfflineCommand("shutdown_harvis", {})

        volume = re.fullmatch(
            r"(?:set )?(?:the )?(?:volume|volumen)(?: to| at| en| al)?\s+(\d{1,3})%?",
            command,
        )
        if volume:
            return OfflineCommand(
                "set_master_volume",
                {"percent": max(0, min(100, int(volume.group(1))))},
            )

        media_action = self._MEDIA_ACTIONS.get(command)
        if media_action:
            return OfflineCommand("media_control", {"action": media_action})

        routine = re.fullmatch(
            r"(?:run|execute|ejecuta|corre)(?: the| la)? (?:routine|rutina) (.+)",
            command,
        )
        if routine:
            return OfflineCommand("run_routine", {"name": routine.group(1)})

        file_search = re.fullmatch(
            r"(?:find|search|busca|encuentra)(?: me)? (.+)",
            command,
        )
        if file_search and any(
            marker in command
            for marker in ("file", "folder", "pdf", "archivo", "carpeta", "document")
        ):
            return OfflineCommand(
                "semantic_search_files",
                {"query": file_search.group(1), "limit": 8},
            )

        named_link = re.fullmatch(
            r"(?:open|abre)(?: the| el| la)? (?:link|enlace) (.+)",
            command,
        )
        if named_link:
            return OfflineCommand("open_named_link", {"name": named_link.group(1)})

        open_match = re.fullmatch(r"(?:open|abre|inicia|launch) (.+)", command)
        if open_match:
            target = open_match.group(1).strip()
            if target in self._SITE_URLS:
                return OfflineCommand("open_url", {"url": self._SITE_URLS[target]})
            if target.startswith(("http://", "https://")):
                return OfflineCommand("open_url", {"url": target})
            if "." in target and " " not in target:
                url = target if "://" in target else f"https://{target}"
                return OfflineCommand("open_url", {"url": url})
            if target.startswith(("file ", "folder ", "archivo ", "carpeta ")):
                name = target.split(" ", 1)[1]
                return OfflineCommand("open_exact_file_or_folder", {"name": name})
            return OfflineCommand("open_application", {"app_name": target})

        web_search = re.fullmatch(
            r"(?:search(?: for)?|busca en google|googlea) (.+)",
            command,
        )
        if web_search:
            return OfflineCommand(
                "open_url",
                {
                    "url": "https://www.google.com/search?q="
                    f"{quote_plus(web_search.group(1))}"
                },
            )
        return None

    def execute(self, text: str, executor: ToolExecutor) -> dict[str, Any] | None:
        parsed = self.parse(text)
        if parsed is None:
            return None
        result = executor(parsed.action, dict(parsed.arguments))
        return {
            "status": str(result.get("status", "completed")),
            "offline": True,
            "action": parsed.action,
            "result": result,
        }


__all__ = ["OfflineCommand", "OfflineCommandRouter"]
