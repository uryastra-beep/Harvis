from pathlib import Path

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
        remote_control_enabled=True,
        remote_control_port=9123,
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
        remote_control_enabled="invalid",  # type: ignore[arg-type]
        remote_control_port=90000,
    )

    store.save(settings)
    loaded = store.load()

    assert loaded.user_name == "Santi Astra"
    assert loaded.voice_volume == 100
    assert loaded.visualizer_type == "Sphere"
    assert loaded.visualizer_sensitivity == 0
    assert loaded.ai_watermark_enabled is True
    assert loaded.remote_control_enabled is False
    assert loaded.remote_control_port == 65535


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
