from pathlib import Path

import pytest

from harvis import config
from harvis.config import HarvisSettings, SettingsStore


def test_settings_round_trip(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    store = SettingsStore(config_path)
    expected = HarvisSettings(
        start_with_windows=True,
        user_name="Santi",
        voice_volume=45,
        microphone_device="System default",
        visualizer_enabled=True,
        visualizer_type="Bars",
        visualizer_sensitivity=82,
        ai_provider="Not configured",
        ai_watermark_enabled=False,
        local_memory_enabled=False,
        local_wake_word_enabled=True,
        wake_session_timeout_seconds=240,
        automatic_update_checks=False,
        system_tray_enabled=False,
        remote_control_enabled=True,
        remote_control_port=9123,
        proactive_enabled=False,
        download_notifications_enabled=False,
        battery_alert_percent=15,
        semantic_file_search_enabled=False,
        visual_memory_enabled=False,
        phone_notifications_enabled=False,
        ui_scale_percent=130,
        reduced_motion=True,
        high_contrast=True,
        captions_enabled=True,
        first_run_completed=True,
    )

    store.save(expected)

    assert store.load() == expected


def test_settings_are_normalized(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    store = SettingsStore(config_path)
    settings = HarvisSettings(
        user_name="   Santi    Astra   ",
        voice_volume=140,
        visualizer_type="Unknown",
        visualizer_sensitivity=-5,
        ai_watermark_enabled="invalid",  # type: ignore[arg-type]
        local_memory_enabled="invalid",  # type: ignore[arg-type]
        local_wake_word_enabled="invalid",  # type: ignore[arg-type]
        wake_session_timeout_seconds=9999,
        automatic_update_checks="invalid",  # type: ignore[arg-type]
        system_tray_enabled="invalid",  # type: ignore[arg-type]
        remote_control_enabled="invalid",  # type: ignore[arg-type]
        remote_control_port=90000,
        proactive_enabled="invalid",  # type: ignore[arg-type]
        download_notifications_enabled="invalid",  # type: ignore[arg-type]
        battery_alert_percent=99,
        semantic_file_search_enabled="invalid",  # type: ignore[arg-type]
        visual_memory_enabled="invalid",  # type: ignore[arg-type]
        phone_notifications_enabled="invalid",  # type: ignore[arg-type]
        ui_scale_percent=999,
        reduced_motion="invalid",  # type: ignore[arg-type]
        high_contrast="invalid",  # type: ignore[arg-type]
        captions_enabled="invalid",  # type: ignore[arg-type]
        first_run_completed="invalid",  # type: ignore[arg-type]
    )

    store.save(settings)
    loaded = store.load()

    assert loaded.user_name == "Santi Astra"
    assert loaded.voice_volume == 100
    assert loaded.visualizer_type == "Sphere"
    assert loaded.visualizer_sensitivity == 0
    assert loaded.ai_watermark_enabled is True
    assert loaded.local_memory_enabled is True
    assert loaded.local_wake_word_enabled is False
    assert loaded.wake_session_timeout_seconds == 600
    assert loaded.automatic_update_checks is True
    assert loaded.system_tray_enabled is True
    assert loaded.remote_control_enabled is False
    assert loaded.remote_control_port == 65535
    assert loaded.proactive_enabled is True
    assert loaded.download_notifications_enabled is True
    assert loaded.battery_alert_percent == 50
    assert loaded.semantic_file_search_enabled is True
    assert loaded.visual_memory_enabled is True
    assert loaded.phone_notifications_enabled is True
    assert loaded.ui_scale_percent == 180
    assert loaded.reduced_motion is False
    assert loaded.high_contrast is False
    assert loaded.captions_enabled is False
    assert loaded.first_run_completed is False


def test_blank_user_name_falls_back_to_user(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    store = SettingsStore(config_path)
    store.save(HarvisSettings(user_name="   "))

    assert store.load().user_name == "User"


def test_ai_watermark_defaults_to_enabled_for_existing_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text('{"user_name": "Santi"}\n', encoding="utf-8")

    loaded = SettingsStore(config_path).load()

    assert loaded.ai_watermark_enabled is True


def test_remote_control_defaults_to_disabled_for_existing_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text('{"user_name": "Santi"}\n', encoding="utf-8")

    loaded = SettingsStore(config_path).load()

    assert loaded.remote_control_enabled is False
    assert loaded.remote_control_port == 8765


def test_failed_atomic_save_preserves_previous_settings(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "settings.json"
    store = SettingsStore(config_path)
    store.save(HarvisSettings(user_name="Before"))

    def fail_replace(source, destination) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(config.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        store.save(HarvisSettings(user_name="After"))

    assert store.load().user_name == "Before"
    assert list(tmp_path.glob(".settings.json.*.tmp")) == []
