from harvis.actions.screen_control import (
    ScreenCapture,
    _normalized_to_screen,
    _parse_vision_response,
)


def test_parse_vision_response() -> None:
    result = _parse_vision_response(
        '{"found":true,"x":750,"y":250,"confidence":0.93,'
        '"description":"send button","sensitive":false}'
    )

    assert result.found is True
    assert result.x_1000 == 750
    assert result.y_1000 == 250
    assert result.confidence == 0.93
    assert result.description == "send button"
    assert result.sensitive is False


def test_normalized_coordinates_support_virtual_screen_origins() -> None:
    capture = ScreenCapture(
        image_bytes=b"",
        origin_x=-1920,
        origin_y=0,
        width=3840,
        height=1080,
    )

    assert _normalized_to_screen(0, 0, capture) == (-1920, 0)
    assert _normalized_to_screen(1000, 1000, capture) == (1919, 1079)
    assert _normalized_to_screen(500, 500, capture) == (0, 540)
