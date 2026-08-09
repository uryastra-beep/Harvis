from harvis.actions.app_discovery import _normalize_name, _score_name


def test_application_name_normalization() -> None:
    assert _normalize_name("  Visual-Studio_Code  ") == "visual studio code"


def test_application_match_prefers_exact_names() -> None:
    assert _score_name("WhatsApp.exe", "whatsapp") > _score_name(
        "WhatsAppUpdater.exe",
        "whatsapp",
    )


def test_application_match_accepts_partial_human_names() -> None:
    assert _score_name("obs64.exe", "obs") >= 300
