from __future__ import annotations

import re
from urllib.parse import quote_plus

from harvis.core.intents import Intent, IntentType

WAKE_WORDS = ("harvis", "jarvis")

_SITE_URLS = {
    "google": "https://www.google.com",
    "browser": "https://www.google.com",
    "youtube": "https://www.youtube.com",
}

_NUMBER_UNITS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

_NUMBER_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def normalize_speech(text: str) -> str:
    normalized = text.lower().strip()
    normalized = re.sub(r"[^a-z0-9%:/._?=&+\-\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def contains_wake_word(text: str) -> bool:
    normalized = normalize_speech(text)
    return any(re.search(rf"\b{re.escape(word)}\b", normalized) for word in WAKE_WORDS)


def extract_command(text: str) -> str | None:
    normalized = normalize_speech(text)

    wake_matches: list[tuple[int, int]] = []
    for wake_word in WAKE_WORDS:
        match = re.search(rf"\b{re.escape(wake_word)}\b", normalized)
        if match is not None:
            wake_matches.append((match.start(), match.end()))

    if not wake_matches:
        return None

    _, wake_end = min(wake_matches, key=lambda item: item[0])
    command = normalized[wake_end:].strip(" ,.-")
    return command


def parse_spoken_intent(text: str) -> Intent | None:
    command = extract_command(text)
    if command is None or not command:
        return None

    volume_intent = _parse_volume_intent(command)
    if volume_intent is not None:
        return volume_intent

    open_intent = _parse_open_intent(command)
    if open_intent is not None:
        return open_intent

    return Intent(IntentType.ASK_AI, {"prompt": command})


def _parse_volume_intent(command: str) -> Intent | None:
    if "volume" not in command:
        return None

    volume_match = re.search(
        r"\bvolume\b(?:\s+(?:to|at))?\s+(.+)$",
        command,
    )
    if volume_match is None:
        return None

    percent = _parse_percent(volume_match.group(1))
    if percent is None:
        return None

    return Intent(IntentType.SET_VOLUME, {"percent": percent})


def _parse_percent(value_text: str) -> int | None:
    cleaned = value_text.replace("%", " ")
    cleaned = re.sub(r"\bpercent\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    digit_match = re.search(r"\b(100|[0-9]{1,2})\b", cleaned)
    if digit_match is not None:
        return int(digit_match.group(1))

    words = cleaned.split()
    if not words:
        return None

    if words == ["one", "hundred"] or words == ["a", "hundred"]:
        return 100

    total = 0
    found = False
    for word in words:
        if word in _NUMBER_TENS:
            total += _NUMBER_TENS[word]
            found = True
            continue
        if word in _NUMBER_UNITS:
            total += _NUMBER_UNITS[word]
            found = True
            continue
        if word in {"and", "the"}:
            continue
        return None

    if not found or total > 100:
        return None

    return total


def _parse_open_intent(command: str) -> Intent | None:
    open_match = re.match(r"^(?:please\s+)?open\s+(.+)$", command)
    if open_match is None:
        return None

    target = open_match.group(1).strip()
    if not target:
        return None

    if target in _SITE_URLS:
        return Intent(
            IntentType.OPEN_URL,
            {
                "url": _SITE_URLS[target],
                "target": target,
            },
        )

    if target.startswith(("http://", "https://")):
        return Intent(IntentType.OPEN_URL, {"url": target, "target": "website"})

    if "." in target and " " not in target:
        url = target if "://" in target else f"https://{target}"
        return Intent(IntentType.OPEN_URL, {"url": url, "target": target})

    search_url = f"https://www.google.com/search?q={quote_plus(target)}"
    return Intent(
        IntentType.OPEN_URL,
        {
            "url": search_url,
            "target": target,
        },
    )
