from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageDraw

from harvis.features.visual_memory import VisualTargetMemory


@dataclass
class _Capture:
    image_bytes: bytes
    origin_x: int = 0
    origin_y: int = 0
    width: int = 400
    height: int = 240


def _capture(*, changed: bool = False) -> _Capture:
    image = Image.new("RGB", (400, 240), "#081235")
    draw = ImageDraw.Draw(image)
    draw.rectangle((160, 90, 240, 140), fill="#ff5577" if changed else "#53eefc")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return _Capture(buffer.getvalue())


def test_visual_memory_requires_repetition_and_matching_pixels(tmp_path) -> None:
    memory = VisualTargetMemory(tmp_path / "visual.json")
    capture = _capture()

    memory.remember("Save button", "left", capture, 200, 115)
    assert memory.recall("Save button", "left", capture) is None

    memory.remember("Save button", "left", capture, 200, 115)
    recalled = memory.recall("Save button", "left", capture)
    assert recalled is not None
    assert recalled["x"] == 200
    assert recalled["successes"] == 2

    assert memory.recall("Save button", "left", _capture(changed=True)) is None


def test_visual_memory_never_stores_sensitive_targets(tmp_path) -> None:
    memory = VisualTargetMemory(tmp_path / "visual.json")
    memory.remember("Buy now", "left", _capture(), 200, 115, sensitive=True)

    assert memory.stats()["targets"] == 0
