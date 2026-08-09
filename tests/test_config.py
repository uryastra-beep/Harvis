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
    )

    store.save(settings)
    loaded = store.load()

    assert loaded.user_name == "Santi Astra"
    assert loaded.voice_volume == 100
    assert loaded.visualizer_type == "Sphere"
    assert loaded.visualizer_sensitivity == 0


def test_blank_user_name_falls_back_to_user(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    store = SettingsStore(config_path)
    store.save(HarvisSettings(user_name="   "))

    assert store.load().user_name == "User"
