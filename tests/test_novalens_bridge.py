import json
import threading
import time

from harvis.actions.system import SystemActionError
from harvis.assistant import HarvisAssistant
from harvis.config import HarvisSettings
from harvis.features.novalens_bridge import NovaLensBridge


def test_novalens_bridge_writes_bounded_request(tmp_path) -> None:
    bridge = NovaLensBridge(tmp_path)

    result = bridge.send("screen")
    payload = json.loads(bridge.request_path.read_text(encoding="utf-8"))

    assert result["status"] == "sent"
    assert payload["version"] == 1
    assert payload["action"] == "screen"
    assert isinstance(payload["created_at"], float)


def test_novalens_bridge_waits_for_matching_response(tmp_path) -> None:
    bridge = NovaLensBridge(tmp_path)

    def responder() -> None:
        while not bridge.request_path.exists():
            time.sleep(0.01)
        request = json.loads(bridge.request_path.read_text(encoding="utf-8"))
        bridge.response_path.write_text(
            json.dumps(
                {
                    "id": request["id"],
                    "status": "completed",
                    "text": "NovaLens answer",
                }
            ),
            encoding="utf-8",
        )

    thread = threading.Thread(target=responder)
    thread.start()
    result = bridge.send("ask", text="Question", wait_for_response=True, timeout_seconds=5)
    thread.join(timeout=2)

    assert result["status"] == "completed"
    assert result["text"] == "NovaLens answer"


def test_companion_action_does_not_claim_success_when_novalens_is_missing(
    monkeypatch,
) -> None:
    assistant = HarvisAssistant(HarvisSettings())

    def missing_known_launcher(name: str) -> None:
        raise SystemActionError(f"{name} is unavailable")

    monkeypatch.setattr("harvis.assistant.open_application", missing_known_launcher)
    monkeypatch.setattr(
        "harvis.assistant.open_discovered_application",
        lambda name: {"status": "not_found", "application": name},
    )
    monkeypatch.setattr(
        assistant._novalens,
        "send",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("The bridge must not send when NovaLens is missing")
        ),
    )

    result = assistant._execute_tool_untracked(
        "novalens_analyze_screen_region",
        {},
    )

    assert result["status"] == "not_found"
    assert "could not be opened" in result["message"]
