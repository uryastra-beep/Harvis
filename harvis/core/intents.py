from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class IntentType(StrEnum):
    OPEN_URL = "open_url"
    SET_VOLUME = "set_volume"
    ASK_AI = "ask_ai"


@dataclass(frozen=True, slots=True)
class Intent:
    type: IntentType
    parameters: dict[str, Any] = field(default_factory=dict)
