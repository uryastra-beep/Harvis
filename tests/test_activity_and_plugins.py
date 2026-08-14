import json

from harvis.features.activity import ActivityHistory
from harvis.features.declarative_plugins import DeclarativePluginStore


def test_activity_redacts_content_and_tracks_safe_undo(tmp_path) -> None:
    history = ActivityHistory(tmp_path / "activity.jsonl")
    history.record(
        "type_text",
        {"text": "private content", "token": "secret"},
        {"status": "completed"},
        undo={"action": "browser_control", "arguments": {"action": "reopen_tab"}},
    )

    entry = history.recent()["entries"][0]
    assert entry["arguments"]["text"] == "<content omitted>"
    assert entry["arguments"]["token"] == "<redacted>"
    assert history.take_undo()["action"] == "browser_control"
    assert history.take_undo() is None


def test_plugins_are_json_data_only(tmp_path) -> None:
    directory = tmp_path / "plugins"
    directory.mkdir()
    (directory / "study.json").write_text(
        json.dumps(
            {
                "name": "Study",
                "description": "Open study tools",
                "steps": [{"action": "open_url", "url": "https://example.com"}],
            }
        ),
        encoding="utf-8",
    )
    (directory / "ignored.py").write_text("raise RuntimeError('must never run')", encoding="utf-8")

    store = DeclarativePluginStore(directory)

    assert store.list()["count"] == 1
    assert store.get("study")["steps"][0]["action"] == "open_url"


def test_plugin_install_and_remove_validate_data_only_manifest(tmp_path) -> None:
    source = tmp_path / "downloaded-plugin.json"
    source.write_text(
        json.dumps(
            {
                "name": "Focus Tools",
                "version": "1.2.0",
                "author": "Test",
                "steps": [{"action": "open_url", "url": "https://example.com"}],
            }
        ),
        encoding="utf-8",
    )
    directory = tmp_path / "installed"
    store = DeclarativePluginStore(directory)
    validated = []

    installed = store.install(
        source,
        validate_steps=lambda steps: validated.append(steps),
    )

    assert installed["status"] == "installed"
    assert validated[0][0]["action"] == "open_url"
    assert store.get("focus tools")["version"] == "1.2.0"
    assert store.remove("Focus Tools")["status"] == "removed"
    assert store.get("Focus Tools") is None
