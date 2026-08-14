from __future__ import annotations

import json
import zipfile

from harvis.features.diagnostics import RuntimeDiagnostics, RuntimeHealthSession


def test_diagnostics_bundle_redacts_secrets(tmp_path, monkeypatch) -> None:
    data = tmp_path / "Harvis"
    data.mkdir()
    (data / "settings.json").write_text(
        json.dumps({"user_name": "Ury", "proactive_enabled": True}),
        encoding="utf-8",
    )
    (data / "harvis.log").write_text(
        "api_key=AIza012345678901234567890123456789\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("harvis.features.diagnostics.get_gemini_api_key", lambda: "configured")
    diagnostics = RuntimeDiagnostics(data, settings_path=data / "settings.json")

    result = diagnostics.export_bundle(tmp_path / "exports")

    with zipfile.ZipFile(result["path"]) as archive:
        settings = archive.read("settings-redacted.json").decode()
        log = archive.read("harvis-log-tail.txt").decode()
    assert "Ury" not in settings
    assert "AIza012345678901234567890123456789" not in log


def test_runtime_health_detects_previous_unclean_shutdown(tmp_path) -> None:
    first = RuntimeHealthSession(tmp_path)
    assert first.start() is False

    second = RuntimeHealthSession(tmp_path)
    assert second.start() is True
    second.stop()
    first.stop()
