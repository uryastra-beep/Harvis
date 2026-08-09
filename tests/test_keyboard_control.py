from __future__ import annotations

import pytest

from harvis.actions.keyboard_control import _validate_text_payload
from harvis.actions.system import SystemActionError


def test_typing_guard_accepts_normal_spanish_punctuation() -> None:
    _validate_text_payload("Hola, ¿cómo estás?")
    _validate_text_payload("Sí!!! Todo bien...")
    _validate_text_payload("Gemini.mm")


def test_typing_guard_rejects_corrupted_punctuation_runs() -> None:
    with pytest.raises(SystemActionError, match="abnormal punctuation run"):
        _validate_text_payload("hola,?????????????Hola, ¿cómo ??????")


def test_typing_guard_rejects_invalid_unicode_replacement_character() -> None:
    with pytest.raises(SystemActionError, match="invalid characters"):
        _validate_text_payload("Hola \ufffd")
