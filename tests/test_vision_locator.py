from harvis.actions.screen_control import ScreenCapture, _normalized_to_screen
from harvis.actions.vision_locator import (
    _detect_image_mime_type,
    _parse_vision_response,
)


def test_parse_vision_bounding_box_uses_center() -> None:
    result = _parse_vision_response(
        '{"found":true,"box_2d":[200,700,300,800],"confidence":0.94,'
        '"description":"send button","sensitive":false}',
        model="gemini-3.6-flash",
    )

    assert result.found is True
    assert result.box_2d == (200, 700, 300, 800)
    assert result.x_1000 == 750
    assert result.y_1000 == 250
    assert result.confidence == 0.94
    assert result.description == "send button"
    assert result.sensitive is False


def test_parse_vision_bounding_box_normalizes_reversed_coordinates() -> None:
    result = _parse_vision_response(
        '{"found":true,"box_2d":[400,600,200,300],"confidence":0.8,'
        '"description":"icon","sensitive":false}'
    )

    assert result.box_2d == (200, 300, 400, 600)
    assert result.x_1000 == 450
    assert result.y_1000 == 300


def test_invalid_zero_area_box_is_not_clickable() -> None:
    result = _parse_vision_response(
        '{"found":true,"box_2d":[100,100,100,100],"confidence":0.99,'
        '"description":"bad box","sensitive":false}'
    )

    assert result.found is False
    assert result.confidence == 0.0


def test_normalized_box_center_maps_to_monitor_origin() -> None:
    capture = ScreenCapture(
        image_bytes=b"",
        origin_x=1920,
        origin_y=0,
        width=1920,
        height=1080,
    )

    result = _parse_vision_response(
        '{"found":true,"box_2d":[450,450,550,550],"confidence":0.9,'
        '"description":"center control","sensitive":false}'
    )

    assert _normalized_to_screen(result.x_1000, result.y_1000, capture) == (2880, 540)


def test_image_mime_detection() -> None:
    assert _detect_image_mime_type(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    assert _detect_image_mime_type(b"\xff\xd8\xffrest") == "image/jpeg"
