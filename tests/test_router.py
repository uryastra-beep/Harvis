import pytest

from harvis.core.intents import Intent, IntentType
from harvis.core.router import IntentRouter


def test_router_opens_url() -> None:
    received: list[str] = []
    router = IntentRouter(browser_action=received.append, volume_action=lambda _: None)

    router.dispatch(Intent(IntentType.OPEN_URL, {"url": "https://www.google.com"}))

    assert received == ["https://www.google.com"]


def test_router_sets_volume() -> None:
    received: list[int] = []
    router = IntentRouter(browser_action=lambda _: None, volume_action=received.append)

    router.dispatch(Intent(IntentType.SET_VOLUME, {"percent": 70}))

    assert received == [70]


def test_router_requires_volume_percent() -> None:
    router = IntentRouter(browser_action=lambda _: None, volume_action=lambda _: None)

    with pytest.raises(ValueError, match="percent"):
        router.dispatch(Intent(IntentType.SET_VOLUME))


def test_ai_intent_is_explicitly_not_implemented() -> None:
    router = IntentRouter(browser_action=lambda _: None, volume_action=lambda _: None)

    with pytest.raises(NotImplementedError):
        router.dispatch(Intent(IntentType.ASK_AI, {"prompt": "Hello"}))
