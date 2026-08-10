from __future__ import annotations

from harvis.actions import visual_control
from harvis.actions.local_vision import (
    LOCAL_CONFIDENCE_THRESHOLD,
    LocalCandidate,
    LocalVisionTarget,
    _merge_candidates,
    parse_target_hints,
)
from harvis.actions.screen_control import ScreenCapture
from harvis.actions.system import SystemActionError
from harvis.actions.vision_locator import VisionTarget


def test_parse_target_hints_extracts_text_color_and_control() -> None:
    hints = parse_target_hints('click the green button that says "New Issue"')

    assert hints.label_hint == "new issue"
    assert hints.control_hint == "button"
    assert hints.colors == ("green",)


def test_parse_target_hints_supports_spanish() -> None:
    hints = parse_target_hints('dale al botón verde que diga "New Issue"')

    assert hints.label_hint == "new issue"
    assert hints.control_hint == "button"
    assert hints.colors == ("green",)


def test_candidate_fusion_rewards_independent_local_methods() -> None:
    accessibility = LocalCandidate(
        left=100,
        top=100,
        right=190,
        bottom=140,
        confidence=0.90,
        label="New Issue",
        methods=("text_label", "accessibility"),
        evidence=("accessible text='New Issue'", "role='Button'"),
    )
    classical_vision = LocalCandidate(
        left=92,
        top=94,
        right=200,
        bottom=146,
        confidence=0.67,
        label="green button",
        methods=("opencv",),
        evidence=("color=green",),
    )

    merged = _merge_candidates([accessibility, classical_vision])

    assert len(merged) == 1
    assert merged[0].confidence > accessibility.confidence
    assert merged[0].confidence >= LOCAL_CONFIDENCE_THRESHOLD
    assert set(merged[0].methods) == {"text_label", "accessibility", "opencv"}


def _capture() -> ScreenCapture:
    return ScreenCapture(
        image_bytes=b"unused",
        origin_x=0,
        origin_y=0,
        width=1920,
        height=1080,
    )


def _local_match() -> LocalVisionTarget:
    return LocalVisionTarget(
        found=True,
        x=640,
        y=420,
        confidence=0.94,
        description="Local match for 'New Issue'.",
        sensitive=False,
        box=(590, 395, 690, 445),
        methods=("text_label", "accessibility", "opencv"),
        diagnostics=(),
    )


def _local_miss() -> LocalVisionTarget:
    return LocalVisionTarget(
        found=False,
        x=0,
        y=0,
        confidence=0.0,
        description="No local visual candidate matched the requested target.",
        sensitive=False,
        box=(0, 0, 0, 0),
        methods=(),
        diagnostics=(),
    )


def _cloud_match() -> VisionTarget:
    return VisionTarget(
        found=True,
        x_1000=500,
        y_1000=500,
        confidence=0.96,
        description="Gemini found the requested control.",
        sensitive=False,
        box_2d=(450, 450, 550, 550),
        model="test-vision-model",
    )


def test_vision_click_prefers_gemini_when_cloud_is_available(monkeypatch) -> None:
    capture = _capture()
    actions: list[tuple[str, object]] = []

    monkeypatch.setattr(visual_control, "capture_preferred_screen", lambda: capture)
    monkeypatch.setattr(
        visual_control,
        "locate_visual_target",
        lambda capture_value, target: _cloud_match(),
    )
    monkeypatch.setattr(
        visual_control,
        "locate_local_target",
        lambda capture_value, target: (_ for _ in ()).throw(
            AssertionError("Local vision must not run after a confident Gemini match.")
        ),
    )
    monkeypatch.setattr(
        visual_control,
        "_move_cursor",
        lambda x, y, duration: actions.append(("move", (x, y, duration))),
    )
    monkeypatch.setattr(
        visual_control,
        "_click_mouse",
        lambda button: actions.append(("click", button)),
    )

    result = visual_control.vision_click('green button that says "New Issue"')

    assert result["status"] == "clicked"
    assert result["locator"] == "gemini"
    assert result["cloud_attempts"] == 1
    assert result["local_attempts"] == 0
    assert actions[-1] == ("click", "left")


def test_vision_click_uses_local_after_gemini_failure(monkeypatch) -> None:
    capture = _capture()
    cloud_calls = 0
    actions: list[tuple[str, object]] = []

    def fail_cloud(capture_value, target):
        nonlocal cloud_calls
        cloud_calls += 1
        raise SystemActionError("quota exceeded")

    monkeypatch.setattr(visual_control, "capture_preferred_screen", lambda: capture)
    monkeypatch.setattr(visual_control, "capture_full_screen", lambda: capture)
    monkeypatch.setattr(visual_control, "locate_visual_target", fail_cloud)
    monkeypatch.setattr(
        visual_control,
        "locate_local_target",
        lambda capture_value, target: _local_match(),
    )
    monkeypatch.setattr(
        visual_control,
        "_move_cursor",
        lambda x, y, duration: actions.append(("move", (x, y, duration))),
    )
    monkeypatch.setattr(
        visual_control,
        "_click_mouse",
        lambda button: actions.append(("click", button)),
    )

    result = visual_control.vision_click('green button that says "New Issue"')

    assert result["status"] == "clicked"
    assert result["locator"] == "local"
    assert result["local_fallback_used"] is True
    assert result["cloud_attempts"] == 1
    assert cloud_calls == 1
    assert result["x"] == 640
    assert result["y"] == 420
    assert actions[-1] == ("click", "left")


def test_vision_click_retries_gemini_after_local_failure(monkeypatch) -> None:
    capture = _capture()
    cloud_calls = 0

    def fail_cloud(capture_value, target):
        nonlocal cloud_calls
        cloud_calls += 1
        raise SystemActionError("quota exceeded")

    monkeypatch.setattr(visual_control, "capture_preferred_screen", lambda: capture)
    monkeypatch.setattr(visual_control, "capture_full_screen", lambda: capture)
    monkeypatch.setattr(visual_control, "locate_visual_target", fail_cloud)
    monkeypatch.setattr(
        visual_control,
        "locate_local_target",
        lambda capture_value, target: _local_miss(),
    )

    result = visual_control.vision_click("unknown visual target")

    assert cloud_calls == 2
    assert result["status"] == "vision_unavailable"
    assert result["description"] == "Could not find it."
    assert result["cloud_error"] == "Gemini Vision unavailable."
    assert "quota exceeded" not in result["cloud_error"]
    assert result["local_fallback_used"] is True
    assert result["cloud_fallback_used"] is True
