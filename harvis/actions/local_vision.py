from __future__ import annotations

import math
import platform
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from harvis.actions.screen_control import ScreenCapture

LOCAL_CONFIDENCE_THRESHOLD = 0.78
MAX_ACCESSIBILITY_ELEMENTS = 1400
TEMPLATE_MATCH_MIN_SCORE = 0.72
TEMPLATE_DIRECTORY = (
    Path(__file__).resolve().parent.parent / "assets" / "vision_templates"
)

_COLOR_ALIASES = {
    "green": "green",
    "verde": "green",
    "blue": "blue",
    "azul": "blue",
    "red": "red",
    "rojo": "red",
    "roja": "red",
    "yellow": "yellow",
    "amarillo": "yellow",
    "amarilla": "yellow",
    "orange": "orange",
    "naranja": "orange",
    "purple": "purple",
    "morado": "purple",
    "morada": "purple",
    "violet": "purple",
    "pink": "pink",
    "rosa": "pink",
    "white": "white",
    "blanco": "white",
    "blanca": "white",
    "black": "black",
    "negro": "black",
    "negra": "black",
    "gray": "gray",
    "grey": "gray",
    "gris": "gray",
}

_CONTROL_ALIASES = {
    "button": "button",
    "boton": "button",
    "botón": "button",
    "icon": "icon",
    "icono": "icon",
    "ícono": "icon",
    "tab": "tab",
    "pestana": "tab",
    "pestaña": "tab",
    "link": "link",
    "enlace": "link",
    "checkbox": "checkbox",
    "casilla": "checkbox",
    "textbox": "edit",
    "input": "edit",
    "campo": "edit",
    "cuadro": "edit",
    "menu": "menu",
    "menú": "menu",
}

_STOP_WORDS = {
    "a",
    "al",
    "and",
    "button",
    "boton",
    "botón",
    "click",
    "clic",
    "dale",
    "de",
    "del",
    "el",
    "en",
    "find",
    "go",
    "haz",
    "icon",
    "icono",
    "ícono",
    "la",
    "le",
    "lo",
    "locate",
    "me",
    "mueve",
    "new",
    "on",
    "press",
    "que",
    "quiero",
    "the",
    "to",
    "ve",
    "where",
    "y",
}

_SENSITIVE_PHRASES = (
    "accept agreement",
    "accept terms",
    "aceptar contrato",
    "aceptar terminos",
    "aceptar términos",
    "borrar cuenta",
    "borrar datos",
    "buy now",
    "checkout",
    "comprar",
    "delete account",
    "delete data",
    "desinstalar",
    "format disk",
    "format drive",
    "formatear",
    "pagar",
    "pay",
    "purchase",
    "send money",
    "transfer money",
    "transferir dinero",
    "uninstall",
)

# HSV ranges use OpenCV's H=0..179 representation.
_HSV_RANGES = {
    "green": (((35, 45, 35), (90, 255, 255)),),
    "blue": (((90, 45, 35), (135, 255, 255)),),
    "red": (
        ((0, 60, 40), (10, 255, 255)),
        ((170, 60, 40), (179, 255, 255)),
    ),
    "yellow": (((18, 60, 60), (36, 255, 255)),),
    "orange": (((5, 70, 60), (22, 255, 255)),),
    "purple": (((130, 40, 35), (169, 255, 255)),),
    "pink": (((155, 35, 55), (179, 255, 255)),),
    "white": (((0, 0, 185), (179, 70, 255)),),
    "black": (((0, 0, 0), (179, 255, 58)),),
    "gray": (((0, 0, 55), (179, 65, 205)),),
}


@dataclass(frozen=True)
class TargetHints:
    original: str
    normalized: str
    label_hint: str
    control_hint: str | None
    colors: tuple[str, ...]


@dataclass(frozen=True)
class LocalCandidate:
    left: int
    top: int
    right: int
    bottom: int
    confidence: float
    label: str
    methods: tuple[str, ...]
    evidence: tuple[str, ...]

    @property
    def center(self) -> tuple[int, int]:
        return (
            int(round((self.left + self.right) / 2)),
            int(round((self.top + self.bottom) / 2)),
        )


@dataclass(frozen=True)
class LocalVisionTarget:
    found: bool
    x: int
    y: int
    confidence: float
    description: str
    sensitive: bool
    box: tuple[int, int, int, int]
    methods: tuple[str, ...]
    diagnostics: tuple[str, ...]


def locate_local_target(capture: ScreenCapture, target: str) -> LocalVisionTarget:
    """Locate a visible UI target without a generative vision model."""

    hints = parse_target_hints(target)
    candidates: list[LocalCandidate] = []
    diagnostics: list[str] = []

    accessibility, accessibility_diagnostic = _accessibility_candidates(
        hints,
        capture,
    )
    candidates.extend(accessibility)
    if accessibility_diagnostic:
        diagnostics.append(accessibility_diagnostic)

    image = _decode_capture(capture)
    if image is None:
        diagnostics.append("OpenCV image decoding is unavailable.")
    else:
        template_candidates, template_diagnostic = _template_candidates(
            image,
            hints,
            capture,
        )
        candidates.extend(template_candidates)
        if template_diagnostic:
            diagnostics.append(template_diagnostic)

        heuristic_candidates, heuristic_diagnostic = _opencv_candidates(
            image,
            hints,
            capture,
        )
        candidates.extend(heuristic_candidates)
        if heuristic_diagnostic:
            diagnostics.append(heuristic_diagnostic)

    merged = _merge_candidates(candidates)
    if not merged:
        return LocalVisionTarget(
            found=False,
            x=0,
            y=0,
            confidence=0.0,
            description="No local visual candidate matched the requested target.",
            sensitive=_looks_sensitive(hints.original),
            box=(0, 0, 0, 0),
            methods=(),
            diagnostics=tuple(diagnostics),
        )

    best = max(merged, key=lambda item: item.confidence)
    x, y = best.center
    method_text = ", ".join(best.methods)
    label_text = best.label or hints.label_hint or hints.original
    description = f"Local match for {label_text!r} using {method_text}."

    return LocalVisionTarget(
        found=True,
        x=x,
        y=y,
        confidence=max(0.0, min(1.0, best.confidence)),
        description=description,
        sensitive=_looks_sensitive(hints.original),
        box=(best.left, best.top, best.right, best.bottom),
        methods=best.methods,
        diagnostics=tuple(diagnostics),
    )


def parse_target_hints(target: str) -> TargetHints:
    original = str(target).strip()
    normalized = _normalize_text(original)
    label_hint = _extract_label_hint(original, normalized)

    tokens = normalized.split()
    control_hint = next(
        (
            _CONTROL_ALIASES[token]
            for token in tokens
            if token in _CONTROL_ALIASES
        ),
        None,
    )

    colors = tuple(
        dict.fromkeys(
            _COLOR_ALIASES[token]
            for token in tokens
            if token in _COLOR_ALIASES
        )
    )

    return TargetHints(
        original=original,
        normalized=normalized,
        label_hint=label_hint,
        control_hint=control_hint,
        colors=colors,
    )


def _extract_label_hint(original: str, normalized: str) -> str:
    quoted = re.findall(r"[\"“”'‘’]([^\"“”'‘’]{1,120})[\"“”'‘’]", original)
    if quoted:
        return _normalize_text(max(quoted, key=len))

    patterns = (
        r"(?:que\s+diga|que\s+dice|que\s+dice\s+el|llamado|llamada)\s+(.+)$",
        r"(?:that\s+says|says|called|named)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip(" .,:;!?")
            if value:
                return value

    tokens = [
        token
        for token in normalized.split()
        if token not in _STOP_WORDS
        and token not in _COLOR_ALIASES
        and token not in _CONTROL_ALIASES
    ]
    return " ".join(tokens).strip()


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value))
    ascii_like = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    ascii_like = ascii_like.casefold()
    ascii_like = re.sub(r"[^a-z0-9]+", " ", ascii_like)
    return " ".join(ascii_like.split())


def _text_similarity(expected: str, actual: str) -> float:
    expected_value = _normalize_text(expected)
    actual_value = _normalize_text(actual)
    if not expected_value or not actual_value:
        return 0.0
    if expected_value == actual_value:
        return 1.0
    if expected_value in actual_value or actual_value in expected_value:
        shorter = min(len(expected_value), len(actual_value))
        longer = max(len(expected_value), len(actual_value))
        containment = shorter / max(1, longer)
        return max(0.78, min(0.97, 0.78 + containment * 0.19))

    expected_tokens = set(expected_value.split())
    actual_tokens = set(actual_value.split())
    overlap = len(expected_tokens & actual_tokens) / max(
        1,
        len(expected_tokens | actual_tokens),
    )
    sequence = SequenceMatcher(None, expected_value, actual_value).ratio()
    return max(overlap, sequence)


def _role_similarity(control_hint: str | None, actual_role: str) -> float:
    if not control_hint:
        return 0.0

    normalized_role = _normalize_text(actual_role)
    expected = {
        "button": {"button", "push button"},
        "icon": {"image", "icon", "button"},
        "tab": {"tab item", "tab"},
        "link": {"hyperlink", "link"},
        "checkbox": {"check box", "checkbox"},
        "edit": {"edit", "document", "text"},
        "menu": {"menu item", "menu"},
    }.get(control_hint, {control_hint})

    if normalized_role in expected:
        return 1.0
    if any(value in normalized_role or normalized_role in value for value in expected):
        return 0.8
    return 0.0


def _accessibility_candidates(
    hints: TargetHints,
    capture: ScreenCapture,
) -> tuple[list[LocalCandidate], str | None]:
    system_name = platform.system()
    if system_name == "Windows":
        return _windows_accessibility_candidates(hints, capture)
    if system_name == "Linux":
        return _linux_accessibility_candidates(hints, capture)
    return [], f"Accessibility scanning is not implemented on {system_name or 'this platform'}."


def _windows_accessibility_candidates(
    hints: TargetHints,
    capture: ScreenCapture,
) -> tuple[list[LocalCandidate], str | None]:
    try:
        from pywinauto import Desktop
    except ImportError:
        return [], "Windows UI Automation requires pywinauto."

    candidates: list[LocalCandidate] = []
    seen = 0

    try:
        windows = Desktop(backend="uia").windows(visible_only=True)
    except Exception as exc:
        return [], f"Windows UI Automation could not enumerate windows: {exc}"

    for window in windows:
        wrappers: Iterable[Any]
        try:
            wrappers = [window, *window.descendants()]
        except Exception:
            wrappers = [window]

        for wrapper in wrappers:
            seen += 1
            if seen > MAX_ACCESSIBILITY_ELEMENTS:
                return candidates, (
                    f"Windows UI Automation stopped after {MAX_ACCESSIBILITY_ELEMENTS} elements."
                )

            try:
                info = wrapper.element_info
                if not bool(getattr(info, "visible", True)):
                    continue

                name = str(getattr(info, "name", "") or "").strip()
                role = str(getattr(info, "control_type", "") or "").strip()
                rectangle = getattr(info, "rectangle", None)
                if rectangle is None:
                    rectangle = wrapper.rectangle()

                left = int(rectangle.left)
                top = int(rectangle.top)
                right = int(rectangle.right)
                bottom = int(rectangle.bottom)
            except Exception:
                continue

            candidate = _candidate_from_accessibility(
                hints,
                name=name,
                role=role,
                box=(left, top, right, bottom),
                capture=capture,
            )
            if candidate is not None:
                candidates.append(candidate)

    return candidates, None


def _linux_accessibility_candidates(
    hints: TargetHints,
    capture: ScreenCapture,
) -> tuple[list[LocalCandidate], str | None]:
    try:
        import pyatspi
    except ImportError:
        return [], (
            "Linux accessibility scanning requires the system pyatspi package "
            "and an AT-SPI desktop session."
        )

    candidates: list[LocalCandidate] = []
    seen = 0

    try:
        desktop = pyatspi.Registry.getDesktop(0)
    except Exception as exc:
        return [], f"Linux AT-SPI could not access the desktop: {exc}"

    stack = [desktop]
    while stack and seen < MAX_ACCESSIBILITY_ELEMENTS:
        node = stack.pop()
        seen += 1

        try:
            name = str(getattr(node, "name", "") or "").strip()
            role = str(node.getRoleName() or "").strip()
            component = node.queryComponent()
            extents = component.getExtents(pyatspi.DESKTOP_COORDS)
            box = (
                int(extents.x),
                int(extents.y),
                int(extents.x + extents.width),
                int(extents.y + extents.height),
            )
            candidate = _candidate_from_accessibility(
                hints,
                name=name,
                role=role,
                box=box,
                capture=capture,
            )
            if candidate is not None:
                candidates.append(candidate)
        except Exception:
            pass

        try:
            child_count = int(node.childCount)
            for index in range(child_count - 1, -1, -1):
                stack.append(node.getChildAtIndex(index))
        except Exception:
            continue

    diagnostic = None
    if seen >= MAX_ACCESSIBILITY_ELEMENTS:
        diagnostic = (
            f"Linux AT-SPI stopped after {MAX_ACCESSIBILITY_ELEMENTS} elements."
        )
    return candidates, diagnostic


def _candidate_from_accessibility(
    hints: TargetHints,
    *,
    name: str,
    role: str,
    box: tuple[int, int, int, int],
    capture: ScreenCapture,
) -> LocalCandidate | None:
    left, top, right, bottom = box
    if right <= left or bottom <= top:
        return None
    if not _box_intersects_capture(box, capture):
        return None

    text_score = _text_similarity(hints.label_hint, name)
    role_score = _role_similarity(hints.control_hint, role)

    if hints.label_hint:
        if text_score < 0.34:
            return None
        confidence = 0.42 + text_score * 0.48
        methods = ["text_label"]
        evidence = [f"accessible text={name!r} ({text_score:.2f})"]
        if role_score > 0:
            confidence += 0.07 * role_score
            methods.append("accessibility")
            evidence.append(f"role={role!r} ({role_score:.2f})")
        elif role:
            evidence.append(f"role={role!r}")
    elif role_score > 0:
        confidence = 0.48 + role_score * 0.18
        methods = ["accessibility"]
        evidence = [f"role={role!r} ({role_score:.2f})"]
    else:
        return None

    return LocalCandidate(
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        confidence=min(0.98, confidence),
        label=name or role,
        methods=tuple(methods),
        evidence=tuple(evidence),
    )


def _box_intersects_capture(
    box: tuple[int, int, int, int],
    capture: ScreenCapture,
) -> bool:
    left, top, right, bottom = box
    capture_right = capture.origin_x + capture.width
    capture_bottom = capture.origin_y + capture.height
    return not (
        right <= capture.origin_x
        or left >= capture_right
        or bottom <= capture.origin_y
        or top >= capture_bottom
    )


def _decode_capture(capture: ScreenCapture):
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    try:
        encoded = np.frombuffer(capture.image_bytes, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    except Exception:
        return None
    return image


def _template_candidates(
    image,
    hints: TargetHints,
    capture: ScreenCapture,
) -> tuple[list[LocalCandidate], str | None]:
    try:
        import cv2
    except ImportError:
        return [], "Template matching requires OpenCV."

    if not TEMPLATE_DIRECTORY.exists():
        return [], "No local vision template directory is present."

    files = [
        path
        for path in TEMPLATE_DIRECTORY.iterdir()
        if path.suffix.casefold() in {".png", ".jpg", ".jpeg", ".bmp"}
    ]
    if not files:
        return [], "No local vision image templates are installed."

    query = hints.label_hint or hints.normalized
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    candidates: list[LocalCandidate] = []

    for path in files:
        alias = _normalize_text(path.stem.replace("__", " "))
        alias_score = _text_similarity(query, alias)
        if query and alias_score < 0.28:
            continue

        template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if template is None or template.size == 0:
            continue

        best_score = -1.0
        best_box: tuple[int, int, int, int] | None = None

        for scale in (0.75, 0.9, 1.0, 1.15, 1.35, 1.6):
            width = max(4, int(round(template.shape[1] * scale)))
            height = max(4, int(round(template.shape[0] * scale)))
            if width >= gray.shape[1] or height >= gray.shape[0]:
                continue

            if width == template.shape[1] and height == template.shape[0]:
                resized = template
            else:
                resized = cv2.resize(
                    template,
                    (width, height),
                    interpolation=cv2.INTER_AREA
                    if scale < 1.0
                    else cv2.INTER_CUBIC,
                )

            result = cv2.matchTemplate(
                gray,
                resized,
                cv2.TM_CCOEFF_NORMED,
            )
            _, max_value, _, max_location = cv2.minMaxLoc(result)
            if float(max_value) > best_score:
                best_score = float(max_value)
                left, top = max_location
                best_box = (
                    left,
                    top,
                    left + resized.shape[1],
                    top + resized.shape[0],
                )

        if best_box is None or best_score < TEMPLATE_MATCH_MIN_SCORE:
            continue

        absolute_box = _image_box_to_screen(best_box, image, capture)
        confidence = min(
            0.98,
            0.54 + best_score * 0.42 + min(0.04, alias_score * 0.04),
        )
        candidates.append(
            LocalCandidate(
                left=absolute_box[0],
                top=absolute_box[1],
                right=absolute_box[2],
                bottom=absolute_box[3],
                confidence=confidence,
                label=path.stem,
                methods=("template",),
                evidence=(
                    f"template={path.name!r} ({best_score:.2f})",
                ),
            )
        )

    return candidates, None


def _opencv_candidates(
    image,
    hints: TargetHints,
    capture: ScreenCapture,
) -> tuple[list[LocalCandidate], str | None]:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return [], "Classical shape and color detection requires OpenCV."

    candidates: list[LocalCandidate] = []
    image_height, image_width = image.shape[:2]
    image_area = max(1, image_width * image_height)

    if hints.colors:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        for color in hints.colors:
            ranges = _HSV_RANGES.get(color, ())
            if not ranges:
                continue

            mask = np.zeros((image_height, image_width), dtype=np.uint8)
            for lower, upper in ranges:
                mask = cv2.bitwise_or(
                    mask,
                    cv2.inRange(
                        hsv,
                        np.array(lower, dtype=np.uint8),
                        np.array(upper, dtype=np.uint8),
                    ),
                )

            kernel = np.ones((3, 3), dtype=np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            candidates.extend(
                _contour_candidates(
                    mask,
                    image,
                    capture,
                    hints,
                    color=color,
                    image_area=image_area,
                )
            )
    elif hints.control_hint == "button":
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 70, 160)
        kernel = np.ones((3, 3), dtype=np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)
        candidates.extend(
            _contour_candidates(
                edges,
                image,
                capture,
                hints,
                color=None,
                image_area=image_area,
            )
        )

    return candidates, None


def _contour_candidates(
    mask,
    image,
    capture: ScreenCapture,
    hints: TargetHints,
    *,
    color: str | None,
    image_area: int,
) -> list[LocalCandidate]:
    import cv2

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    candidates: list[LocalCandidate] = []

    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if width < 14 or height < 10:
            continue

        box_area = width * height
        area_ratio = box_area / max(1, image_area)
        if area_ratio < 0.000025 or area_ratio > 0.28:
            continue

        aspect = width / max(1.0, float(height))
        if hints.control_hint == "button" and not (1.0 <= aspect <= 12.0):
            continue
        if hints.control_hint == "icon" and not (0.45 <= aspect <= 2.2):
            continue

        contour_area = float(cv2.contourArea(contour))
        extent = contour_area / max(1.0, float(box_area))
        perimeter = float(cv2.arcLength(contour, True))
        polygon = cv2.approxPolyDP(
            contour,
            0.035 * perimeter if perimeter > 0 else 0.0,
            True,
        )
        rectangularity = 1.0 if 4 <= len(polygon) <= 6 else 0.35
        aspect_fit = _aspect_fit(hints.control_hint, aspect)
        size_fit = min(1.0, math.sqrt(area_ratio / 0.015))

        confidence = (
            0.30
            + min(0.16, extent * 0.16)
            + aspect_fit * 0.09
            + size_fit * 0.05
            + rectangularity * 0.06
        )
        if color is not None:
            confidence += 0.07

        confidence = min(0.69, confidence)
        absolute_box = _image_box_to_screen(
            (x, y, x + width, y + height),
            image,
            capture,
        )
        label = f"{color or 'shape'} {hints.control_hint or 'region'}"
        evidence = (
            f"color={color}" if color else "edge rectangle",
            f"extent={extent:.2f}",
            f"aspect={aspect:.2f}",
        )
        candidates.append(
            LocalCandidate(
                left=absolute_box[0],
                top=absolute_box[1],
                right=absolute_box[2],
                bottom=absolute_box[3],
                confidence=confidence,
                label=label,
                methods=("opencv",),
                evidence=evidence,
            )
        )

    return candidates


def _aspect_fit(control_hint: str | None, aspect: float) -> float:
    if control_hint == "button":
        if 1.4 <= aspect <= 8.0:
            return 1.0
        if 1.0 <= aspect <= 12.0:
            return 0.6
        return 0.15
    if control_hint == "icon":
        return max(0.0, 1.0 - abs(math.log(max(0.01, aspect))) / 1.3)
    return 0.55


def _image_box_to_screen(
    box: tuple[int, int, int, int],
    image,
    capture: ScreenCapture,
) -> tuple[int, int, int, int]:
    image_height, image_width = image.shape[:2]
    scale_x = capture.width / max(1.0, float(image_width))
    scale_y = capture.height / max(1.0, float(image_height))
    left, top, right, bottom = box
    return (
        capture.origin_x + int(round(left * scale_x)),
        capture.origin_y + int(round(top * scale_y)),
        capture.origin_x + int(round(right * scale_x)),
        capture.origin_y + int(round(bottom * scale_y)),
    )


def _merge_candidates(candidates: list[LocalCandidate]) -> list[LocalCandidate]:
    groups: list[list[LocalCandidate]] = []

    for candidate in sorted(
        candidates,
        key=lambda item: item.confidence,
        reverse=True,
    ):
        matched_group = None
        for group in groups:
            if any(_boxes_match(candidate, existing) for existing in group):
                matched_group = group
                break
        if matched_group is None:
            groups.append([candidate])
        else:
            matched_group.append(candidate)

    merged: list[LocalCandidate] = []
    for group in groups:
        primary = max(group, key=lambda item: item.confidence)
        methods = tuple(
            dict.fromkeys(
                method
                for item in group
                for method in item.methods
            )
        )
        evidence = tuple(
            detail
            for item in group
            for detail in item.evidence
        )
        confidence = primary.confidence

        additional_methods = max(0, len(methods) - len(primary.methods))
        confidence += min(0.14, additional_methods * 0.055)

        method_set = set(methods)
        if {"text_label", "opencv"} <= method_set:
            confidence += 0.06
        if {"accessibility", "template"} <= method_set:
            confidence += 0.05
        if {"text_label", "template"} <= method_set:
            confidence += 0.05

        merged.append(
            LocalCandidate(
                left=primary.left,
                top=primary.top,
                right=primary.right,
                bottom=primary.bottom,
                confidence=min(0.99, confidence),
                label=primary.label,
                methods=methods,
                evidence=evidence,
            )
        )

    return merged


def _boxes_match(first: LocalCandidate, second: LocalCandidate) -> bool:
    if _intersection_over_union(first, second) >= 0.22:
        return True

    first_x, first_y = first.center
    second_x, second_y = second.center

    first_width = max(1, first.right - first.left)
    first_height = max(1, first.bottom - first.top)
    second_width = max(1, second.right - second.left)
    second_height = max(1, second.bottom - second.top)

    distance = math.hypot(first_x - second_x, first_y - second_y)
    tolerance = max(
        18.0,
        min(
            max(first_width, first_height),
            max(second_width, second_height),
        )
        * 0.70,
    )
    return distance <= tolerance


def _intersection_over_union(
    first: LocalCandidate,
    second: LocalCandidate,
) -> float:
    left = max(first.left, second.left)
    top = max(first.top, second.top)
    right = min(first.right, second.right)
    bottom = min(first.bottom, second.bottom)

    intersection = max(0, right - left) * max(0, bottom - top)
    if intersection <= 0:
        return 0.0

    first_area = max(1, first.right - first.left) * max(
        1,
        first.bottom - first.top,
    )
    second_area = max(1, second.right - second.left) * max(
        1,
        second.bottom - second.top,
    )
    union = first_area + second_area - intersection
    return intersection / max(1.0, float(union))


def _looks_sensitive(target: str) -> bool:
    normalized = _normalize_text(target)
    return any(
        _normalize_text(phrase) in normalized
        for phrase in _SENSITIVE_PHRASES
    )


__all__ = [
    "LOCAL_CONFIDENCE_THRESHOLD",
    "LocalCandidate",
    "LocalVisionTarget",
    "TargetHints",
    "locate_local_target",
    "parse_target_hints",
]
