from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from harvis.ui.theme import TERTIARY
from harvis.ui.visualizer_window import SphereVisualizer


class TransparentSphereVisualizer(SphereVisualizer):
    """Render the live Harvis sphere without an opaque window background."""

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
        self._microphone_muted = False
        self.setMinimumSize(1, 1)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAutoFillBackground(False)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        width = float(self.width())
        height = float(self.height())
        center = QPointF(width * 0.5, height * 0.5)
        radius = min(width, height) * 0.27

        self._draw_glow(painter, center, radius)
        self._draw_particle_sphere(painter, center, radius)
        self._draw_outer_ring(painter, center, radius)

        if self._microphone_muted:
            span = radius * 0.78
            painter.setPen(
                QPen(
                    QColor(TERTIARY),
                    5.0,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
            )
            painter.drawLine(
                QPointF(center.x() - span, center.y() - span),
                QPointF(center.x() + span, center.y() + span),
            )

    def set_microphone_muted(self, muted: bool) -> None:
        self._microphone_muted = bool(muted)
        self.update()


class OrbPopupWindow(QWidget):
    """Small always-on-top transparent live sphere popup."""

    clicked = Signal()
    DEFAULT_SIZE = 196

    def __init__(
        self,
        sensitivity: int = 60,
        *,
        demo_mode: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        super().__init__(parent, flags)

        self.setWindowTitle("Harvis Orb")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setFixedSize(self.DEFAULT_SIZE, self.DEFAULT_SIZE)

        self.visualizer = TransparentSphereVisualizer(
            sensitivity=sensitivity,
            demo_mode=demo_mode,
            parent=self,
        )
        self.visualizer.setGeometry(self.rect())

        self._drag_offset: QPoint | None = None
        self._press_global_position: QPoint | None = None
        self._dragging = False
        self._user_positioned = False

    def showEvent(self, event) -> None:
        if not self._user_positioned:
            self._move_to_default_position()
        super().showEvent(event)

    def resizeEvent(self, event) -> None:
        self.visualizer.setGeometry(self.rect())
        super().resizeEvent(event)

    def _move_to_default_position(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return

        geometry = screen.availableGeometry()
        x = geometry.center().x() - self.width() // 2
        y = geometry.center().y() - self.height() // 2
        self.move(x, y)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            global_position = event.globalPosition().toPoint()
            self._drag_offset = global_position - self.frameGeometry().topLeft()
            self._press_global_position = global_position
            self._dragging = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._drag_offset is not None
            and self._press_global_position is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            global_position = event.globalPosition().toPoint()
            distance = (global_position - self._press_global_position).manhattanLength()
            if distance >= QApplication.startDragDistance():
                self._dragging = True

            if self._dragging:
                self.move(global_position - self._drag_offset)
                self._user_positioned = True
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            was_click = self._drag_offset is not None and not self._dragging
            self._drag_offset = None
            self._press_global_position = None
            self._dragging = False
            event.accept()
            if was_click:
                self.clicked.emit()
            return
        super().mouseReleaseEvent(event)

    def set_audio_level(self, level: float) -> None:
        self.visualizer.set_audio_level(level)

    def set_sensitivity(self, sensitivity: int) -> None:
        self.visualizer.set_sensitivity(sensitivity)

    def set_demo_mode(self, enabled: bool) -> None:
        self.visualizer.set_demo_mode(enabled)

    def set_spectrum(self, values) -> None:
        return

    def set_microphone_muted(self, muted: bool) -> None:
        self.visualizer.set_microphone_muted(muted)
