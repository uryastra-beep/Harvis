import json

from harvis import update_checker
from harvis.voice.local_wake import LocalWakeWordController


class _ListenerStub:
    is_ready = True

    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _ResponseStub:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self, limit: int = -1) -> bytes:
        del limit
        return json.dumps(self._payload).encode("utf-8")


def test_local_wake_ignores_unaddressed_text_and_stops_after_wake() -> None:
    heard: list[str] = []
    controller = LocalWakeWordController(heard.append)
    listener = _ListenerStub()
    controller._listener = listener

    controller._handle_text("open the browser")
    assert heard == []
    assert not listener.stopped

    controller._handle_text("Harvis open the browser")
    assert heard == ["Harvis open the browser"]
    assert listener.stopped
    assert controller._listener is None


def test_update_checker_reports_newer_semantic_release(monkeypatch) -> None:
    payload = {
        "tag_name": "v9.8.7",
        "html_url": "https://github.com/uryastra-beep/Harvis/releases/tag/v9.8.7",
        "name": "Harvis 9.8.7",
    }
    monkeypatch.setattr(
        update_checker.urllib.request,
        "urlopen",
        lambda request, timeout: _ResponseStub(payload),
    )

    result = update_checker.check_for_updates()

    assert result.available
    assert result.latest_version == "9.8.7"
    assert result.release_name == "Harvis 9.8.7"
