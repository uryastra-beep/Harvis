from __future__ import annotations

from collections.abc import Callable
from typing import Any

from harvis.actions.system import open_default_browser, set_master_volume
from harvis.core.intents import Intent, IntentType


class IntentRouter:
    def __init__(
        self,
        browser_action: Callable[[str], None] = open_default_browser,
        volume_action: Callable[[int], None] = set_master_volume,
    ) -> None:
        self._browser_action = browser_action
        self._volume_action = volume_action

    def dispatch(self, intent: Intent) -> Any:
        if intent.type is IntentType.OPEN_URL:
            url = str(intent.parameters.get("url", "")).strip()
            if not url:
                raise ValueError("The open_url intent requires a URL.")
            return self._browser_action(url)

        if intent.type is IntentType.SET_VOLUME:
            if "percent" not in intent.parameters:
                raise ValueError("The set_volume intent requires a percent value.")
            return self._volume_action(int(intent.parameters["percent"]))

        if intent.type is IntentType.ASK_AI:
            raise NotImplementedError("AI provider integration has not been implemented yet.")

        raise ValueError(f"Unsupported intent type: {intent.type}")
