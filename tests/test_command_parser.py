from harvis.core.command_parser import (
    contains_wake_word,
    extract_command,
    parse_spoken_intent,
)
from harvis.core.intents import IntentType


def test_wake_word_detection_accepts_harvis_and_jarvis() -> None:
    assert contains_wake_word("Harvis open Google")
    assert contains_wake_word("Jarvis set volume to 70 percent")
    assert not contains_wake_word("Open Google")


def test_extract_command_ignores_text_before_wake_word() -> None:
    assert extract_command("Hey Harvis open Google") == "open google"


def test_parse_open_google() -> None:
    intent = parse_spoken_intent("Harvis open Google")

    assert intent is not None
    assert intent.type is IntentType.OPEN_URL
    assert intent.parameters["url"] == "https://www.google.com"


def test_parse_numeric_volume() -> None:
    intent = parse_spoken_intent("Harvis set volume to 70 percent")

    assert intent is not None
    assert intent.type is IntentType.SET_VOLUME
    assert intent.parameters["percent"] == 70


def test_parse_spoken_number_volume() -> None:
    intent = parse_spoken_intent("Jarvis set volume to seventy five percent")

    assert intent is not None
    assert intent.type is IntentType.SET_VOLUME
    assert intent.parameters["percent"] == 75


def test_unknown_command_routes_to_ai() -> None:
    intent = parse_spoken_intent("Harvis explain quantum computing")

    assert intent is not None
    assert intent.type is IntentType.ASK_AI
    assert intent.parameters["prompt"] == "explain quantum computing"
