from __future__ import annotations

import math
import time
from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from harvis.ui.theme import PRIMARY, SECONDARY, TERTIARY


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class AudioReactiveVisualizer(QWidget):
    """Base class for Harvis visualizers driven by a normalized audio level."""

    FRAME_INTERVAL_MS = 16
    LIVE_AUDIO_TIMEOUT_SECONDS = 0.16

    def __init__(
        self,
        sensitivity: int = 60,
        *,
        demo_mode: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._sensitivity = max(0, min(100, int(sensitivity)))
        self._level = 0.0
        self._target_level = 0.0
        self._phase = 0.0
        self._demo_mode = bool(demo_mode)
        self._last_audio_update = 0.0

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(self.FRAME_INTERVAL_MS)
        self._timer.timeout.connect(self._advance_frame)
        self._timer.start()

        self.setMinimumSize(560, 360)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    @property
    def level(self) -> float:
        return self._level

    @property
    def phase(self) -> float:
        return self._phase

    @property
    def sensitivity(self) -> float:
        return self._sensitivity / 100.0

    @property
    def sensitivity_percent(self) -> int:
        return self._sensitivity

    @property
    def demo_mode(self) -> bool:
        return self._demo_mode

    def set_audio_level(self, level: float) -> None:
        """Set the current voice amplitude as a normalized value from 0.0 to 1.0."""

        self._target_level = _clamp01(level)
        self._last_audio_update = time.monotonic()

    def set_sensitivity(self, sensitivity: int) -> None:
        self._sensitivity = max(0, min(100, int(sensitivity)))

    def set_demo_mode(self, enabled: bool) -> None:
        self._demo_mode = bool(enabled)

    def _advance_frame(self) -> None:
        self._phase += 0.045

        if self._demo_mode:
            pulse = (
                0.32
                + 0.22 * math.sin(self._phase * 1.8)
                + 0.17 * math.sin(self._phase * 4.6 + 0.7)
                + 0.09 * math.sin(self._phase * 8.4 + 1.9)
            )
            self._target_level = _clamp01(abs(pulse))
        elif (
            self._target_level > 0.0
            and time.monotonic() - self._last_audio_update
            > self.LIVE_AUDIO_TIMEOUT_SECONDS
        ):
            self._target_level *= 0.72
            if self._target_level < 0.004:
                self._target_level = 0.0

        effective_target = _clamp01(
            self._target_level * (0.55 + self.sensitivity * 0.85)
        )
        smoothing = 0.24 if effective_target >= self._level else 0.11
        self._level += (effective_target - self._level) * smoothing

        self._on_frame()
        self.update()

    def _on_frame(self) -> None:
        pass


class SphereVisualizer(AudioReactiveVisualizer):
    """Harvis sphere visualizer using the official secondary and tertiary colors."""

    LATITUDE_COUNT = 18
    LONGITUDE_COUNT = 34
    OUTER_POINTS = 220

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(PRIMARY))

        width = float(self.width())
        height = float(self.height())
        center = QPointF(width * 0.5, height * 0.5)
        radius = min(width, height) * 0.34

        self._draw_glow(painter, center, radius)
        self._draw_particle_sphere(painter, center, radius)
        self._draw_outer_ring(painter, center, radius)

    def _draw_glow(self, painter: QPainter, center: QPointF, radius: float) -> None:
        glow = QRadialGradient(center, radius * 1.42)
        secondary = QColor(SECONDARY)
        glow.setColorAt(
            0.0,
            QColor(
                secondary.red(),
                secondary.green(),
                secondary.blue(),
                int(20 + self.level * 18),
            ),
        )
        glow.setColorAt(
            0.72,
            QColor(
                secondary.red(),
                secondary.green(),
                secondary.blue(),
                int(10 + self.level * 20),
            ),
        )
        glow.setColorAt(
            1.0,
            QColor(secondary.red(), secondary.green(), secondary.blue(), 0),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(center, radius * 1.42, radius * 1.42)

    def _draw_outer_ring(
        self,
        painter: QPainter,
        center: QPointF,
        radius: float,
    ) -> None:
        path = QPainterPath()

        for index in range(self.OUTER_POINTS + 1):
            angle = (index / self.OUTER_POINTS) * math.tau
            deformation = (
                0.016 * math.sin(angle * 3.0 + self.phase * 0.8)
                + 0.012 * math.sin(angle * 7.0 - self.phase * 1.25)
                + self.level
                * (
                    0.052 * math.sin(angle * 5.0 + self.phase * 3.2)
                    + 0.024 * math.sin(angle * 11.0 - self.phase * 2.4)
                )
            )
            local_radius = radius * (1.0 + deformation)
            point = QPointF(
                center.x() + math.cos(angle) * local_radius,
                center.y() + math.sin(angle) * local_radius,
            )

            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)

        secondary = QColor(SECONDARY)

        for width, alpha in (
            (16.0 + self.level * 8.0, 22),
            (9.0 + self.level * 5.0, 42),
            (4.6 + self.level * 2.5, 105),
        ):
            painter.setPen(
                QPen(
                    QColor(
                        secondary.red(),
                        secondary.green(),
                        secondary.blue(),
                        alpha,
                    ),
                    width,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        painter.setPen(
            QPen(
                QColor(SECONDARY),
                2.3 + self.level * 1.5,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawPath(path)

    def _draw_particle_sphere(
        self,
        painter: QPainter,
        center: QPointF,
        radius: float,
    ) -> None:
        base_color = QColor(TERTIARY)
        rotation = self.phase * 0.16
        tilt = -0.18

        cos_rotation = math.cos(rotation)
        sin_rotation = math.sin(rotation)
        cos_tilt = math.cos(tilt)
        sin_tilt = math.sin(tilt)

        for latitude_index in range(self.LATITUDE_COUNT):
            phi = (
                -math.pi / 2
                + ((latitude_index + 0.5) / self.LATITUDE_COUNT) * math.pi
            )
            cos_phi = math.cos(phi)
            sin_phi = math.sin(phi)

            for longitude_index in range(self.LONGITUDE_COUNT):
                theta = (
                    (longitude_index / self.LONGITUDE_COUNT) * math.tau
                    + (latitude_index % 2) * 0.035
                )

                wave = 1.0 + self.level * (
                    0.065 * math.sin(
                        theta * 3.0 + phi * 4.0 + self.phase * 2.7
                    )
                    + 0.03 * math.sin(theta * 7.0 - self.phase * 1.8)
                )

                x = cos_phi * math.cos(theta) * wave
                y = sin_phi * wave
                z = cos_phi * math.sin(theta) * wave

                rotated_x = x * cos_rotation - z * sin_rotation
                rotated_z = x * sin_rotation + z * cos_rotation

                tilted_y = y * cos_tilt - rotated_z * sin_tilt
                tilted_z = y * sin_tilt + rotated_z * cos_tilt

                perspective = 0.9 + tilted_z * 0.08
                projected_x = (
                    center.x() + rotated_x * radius * 0.82 * perspective
                )
                projected_y = (
                    center.y() + tilted_y * radius * 0.82 * perspective
                )

                depth = _clamp01((tilted_z + 1.0) * 0.5)
                alpha = int(58 + depth * 172)
                size = 0.85 + depth * 1.5 + self.level * 0.55

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(
                    QColor(
                        base_color.red(),
                        base_color.green(),
                        base_color.blue(),
                        alpha,
                    )
                )
                painter.drawEllipse(
                    QPointF(projected_x, projected_y),
                    size,
                    size,
                )


class BarsVisualizer(AudioReactiveVisualizer):
    """Harvis bar visualizer using only the primary and secondary colors."""

    BAR_COUNT = 42
    SPECTRUM_TIMEOUT_SECONDS = 0.18

    def __init__(
        self,
        sensitivity: int = 60,
        *,
        demo_mode: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            sensitivity=sensitivity,
            demo_mode=demo_mode,
            parent=parent,
        )
        self._bars = [0.08 for _ in range(self.BAR_COUNT)]
        self._spectrum: list[float] | None = None
        self._last_spectrum_update = 0.0

    def set_spectrum(self, values: Sequence[float] | None) -> None:
        """Provide normalized spectrum bins. Pass None to return to level-based motion."""

        if values is None:
            self._spectrum = None
            return

        cleaned = [_clamp01(value) for value in values]
        self._spectrum = cleaned or None
        self._last_spectrum_update = time.monotonic()

    def _on_frame(self) -> None:
        spectrum_is_live = (
            self._spectrum is not None
            and time.monotonic() - self._last_spectrum_update
            <= self.SPECTRUM_TIMEOUT_SECONDS
        )

        if not spectrum_is_live and self._spectrum is not None:
            self._spectrum = None

        for index in range(self.BAR_COUNT):
            if self._spectrum:
                source_index = int(
                    (index / max(1, self.BAR_COUNT - 1))
                    * max(0, len(self._spectrum) - 1)
                )
                target = self._spectrum[source_index] * (
                    0.55 + self.sensitivity * 0.75
                )
            else:
                normalized = index / max(1, self.BAR_COUNT - 1)
                wave = (
                    0.52
                    + 0.26 * math.sin(
                        self.phase * 3.1 + normalized * 16.0
                    )
                    + 0.18 * math.sin(
                        self.phase * 5.7 - normalized * 29.0
                    )
                )
                frequency_shape = 0.78 + 0.22 * math.sin(
                    normalized * math.pi
                )
                target = 0.08 + abs(wave) * self.level * frequency_shape

            target = _clamp01(target)
            smoothing = 0.34 if target >= self._bars[index] else 0.16
            self._bars[index] += (target - self._bars[index]) * smoothing

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(PRIMARY))

        width = float(self.width())
        height = float(self.height())
        horizontal_margin = width * 0.045
        top_margin = height * 0.12
        bottom_margin = height * 0.08
        usable_width = width - horizontal_margin * 2.0
        usable_height = height - top_margin - bottom_margin

        gap = max(3.0, usable_width * 0.004)
        bar_width = max(
            3.0,
            (usable_width - gap * (self.BAR_COUNT - 1)) / self.BAR_COUNT,
        )
        total_width = (
            bar_width * self.BAR_COUNT + gap * (self.BAR_COUNT - 1)
        )
        start_x = (width - total_width) * 0.5
        baseline = height - bottom_margin

        secondary = QColor(SECONDARY)

        for index, value in enumerate(self._bars):
            bar_height = max(12.0, usable_height * (0.08 + value * 0.92))
            x = start_x + index * (bar_width + gap)
            y = baseline - bar_height
            radius = min(bar_width * 0.5, 5.0)

            glow_rect = QRectF(
                x - 2.0,
                y - 2.0,
                bar_width + 4.0,
                bar_height + 4.0,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(
                QColor(
                    secondary.red(),
                    secondary.green(),
                    secondary.blue(),
                    34,
                )
            )
            painter.drawRoundedRect(
                glow_rect,
                radius + 2.0,
                radius + 2.0,
            )

            bar_rect = QRectF(x, y, bar_width, bar_height)
            painter.setBrush(secondary)
            painter.drawRoundedRect(bar_rect, radius, radius)


class VisualizerWindow(QWidget):
    """Standalone Harvis visualizer surface for live Gemini voice audio."""

    def __init__(
        self,
        visualizer_type: str = "Sphere",
        sensitivity: int = 60,
        *,
        demo_mode: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Harvis Visualizer")
        self.resize(960, 600)
        self.setMinimumSize(640, 420)
        self.setStyleSheet(f"background-color: {PRIMARY};")

        self._visualizer_type = self._normalize_type(visualizer_type)
        self._sensitivity = max(0, min(100, int(sensitivity)))
        self._demo_mode = bool(demo_mode)
        self.visualizer = self._create_visualizer(self._visualizer_type)
        self.visualizer.setGeometry(self.rect())

    @staticmethod
    def _normalize_type(visualizer_type: str) -> str:
        return "Bars" if visualizer_type.strip().lower() == "bars" else "Sphere"

    def _create_visualizer(self, visualizer_type: str) -> AudioReactiveVisualizer:
        if visualizer_type == "Bars":
            return BarsVisualizer(
                sensitivity=self._sensitivity,
                demo_mode=self._demo_mode,
                parent=self,
            )

        return SphereVisualizer(
            sensitivity=self._sensitivity,
            demo_mode=self._demo_mode,
            parent=self,
        )

    def resizeEvent(self, event) -> None:
        self.visualizer.setGeometry(self.rect())
        super().resizeEvent(event)

    def set_visualizer_type(self, visualizer_type: str) -> None:
        normalized_type = self._normalize_type(visualizer_type)
        if normalized_type == self._visualizer_type:
            return

        previous_level = self.visualizer.level
        old_visualizer = self.visualizer
        self._visualizer_type = normalized_type
        self.visualizer = self._create_visualizer(normalized_type)
        self.visualizer.setGeometry(self.rect())
        self.visualizer.set_audio_level(previous_level)
        self.visualizer.show()
        old_visualizer.hide()
        old_visualizer.deleteLater()

    def set_audio_level(self, level: float) -> None:
        self.visualizer.set_audio_level(level)

    def set_sensitivity(self, sensitivity: int) -> None:
        self._sensitivity = max(0, min(100, int(sensitivity)))
        self.visualizer.set_sensitivity(self._sensitivity)

    def set_demo_mode(self, enabled: bool) -> None:
        self._demo_mode = bool(enabled)
        self.visualizer.set_demo_mode(enabled)

    def set_spectrum(self, values: Sequence[float] | None) -> None:
        if isinstance(self.visualizer, BarsVisualizer):
            self.visualizer.set_spectrum(values)
