from harvis.ui.silent_popup import SilentCommandPopup


def test_visual_search_status_hides_target_text() -> None:
    assert (
        SilentCommandPopup._safe_status_text(
            "Looking for on-screen target: GitHub tab"
        )
        == "Searching..."
    )


def test_visual_click_statuses_remain_generic() -> None:
    assert (
        SilentCommandPopup._safe_status_text(
            "Clicked on-screen target: green New Issue button"
        )
        == "Done."
    )
    assert (
        SilentCommandPopup._safe_status_text(
            "Could not confidently click: WhatsApp icon"
        )
        == "Could not find it."
    )
    assert (
        SilentCommandPopup._safe_status_text(
            "Confirmation required before clicking: Delete repository"
        )
        == "Confirmation required."
    )


def test_non_visual_status_is_preserved() -> None:
    assert (
        SilentCommandPopup._safe_status_text("Gemini Live ready")
        == "Gemini Live ready"
    )
