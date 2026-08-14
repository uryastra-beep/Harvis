from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QParallelAnimationGroup,
    QPointF,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QFrame,
    QFormLayout,
    QGraphicsBlurEffect,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from harvis.config import HarvisSettings, SettingsStore
from harvis.ui.theme import (
    PRIMARY,
    SECONDARY,
    TEXT_PRIMARY,
    build_app_stylesheet,
)


class LiquidBackground(QWidget):
    """Paint the deep Harvis backdrop with subtle Apple-like glass lighting."""

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.fillRect(self.rect(), QColor(PRIMARY))

        width = max(1, self.width())
        height = max(1, self.height())

        upper_glow = QRadialGradient(
            QPointF(width * 0.22, height * 0.08),
            max(width, height) * 0.78,
        )
        upper_glow.setColorAt(0.0, QColor(133, 177, 255, 48))
        upper_glow.setColorAt(0.46, QColor(133, 177, 255, 16))
        upper_glow.setColorAt(1.0, QColor(133, 177, 255, 0))
        painter.fillRect(self.rect(), upper_glow)

        lower_glow = QRadialGradient(
            QPointF(width * 0.92, height * 0.92),
            max(width, height) * 0.62,
        )
        lower_glow.setColorAt(0.0, QColor(83, 238, 252, 32))
        lower_glow.setColorAt(0.5, QColor(83, 238, 252, 10))
        lower_glow.setColorAt(1.0, QColor(83, 238, 252, 0))
        painter.fillRect(self.rect(), lower_glow)

        sheen = QLinearGradient(0, 0, width, height)
        sheen.setColorAt(0.0, QColor(255, 255, 255, 9))
        sheen.setColorAt(0.34, QColor(255, 255, 255, 0))
        sheen.setColorAt(1.0, QColor(255, 255, 255, 4))
        painter.fillRect(self.rect(), sheen)

        super().paintEvent(event)


class _SnapshotLayer(QWidget):
    """Render a page snapshot with independent blur and opacity effects."""

    def __init__(self, parent: QWidget, pixmap) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._label = QLabel(self)
        self._label.setPixmap(pixmap)
        self._label.setScaledContents(True)

        self.blur_effect = QGraphicsBlurEffect(self._label)
        self.blur_effect.setBlurHints(QGraphicsBlurEffect.BlurHint.AnimationHint)
        self._label.setGraphicsEffect(self.blur_effect)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

    def resizeEvent(self, event) -> None:
        self._label.setGeometry(self.rect())
        super().resizeEvent(event)


class AnimatedStackedWidget(QStackedWidget):
    """Travel through intermediate pages with fast glassy motion blur."""

    INTERMEDIATE_DURATION_MS = 72
    FINAL_DURATION_MS = 205
    INTERMEDIATE_BLUR_RADIUS = 14.0
    FINAL_BLUR_RADIUS = 9.0
    SLIDE_DISTANCE = 48

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._transition_group: QParallelAnimationGroup | None = None
        self._transition_layers: list[_SnapshotLayer] = []
        self._route: list[int] = []
        self._active_step_target: int | None = None
        self._pending_target: int | None = None
        self._reduced_motion = False

    def set_reduced_motion(self, reduced: bool) -> None:
        self._reduced_motion = bool(reduced)

    def setCurrentIndexAnimated(self, index: int) -> None:
        if index < 0 or index >= self.count():
            return

        if self._reduced_motion:
            if self._transition_group is not None:
                self._transition_group.stop()
                self._transition_group = None
            self._route = []
            self._pending_target = None
            super().setCurrentIndex(index)
            return

        if self._transition_group is not None:
            self._pending_target = index
            return

        if index == self.currentIndex():
            return

        self._pending_target = None
        self._route = self._build_route(self.currentIndex(), index)
        self._run_next_step()

    @staticmethod
    def _build_route(current_index: int, target_index: int) -> list[int]:
        if current_index == target_index:
            return []

        direction = 1 if target_index > current_index else -1
        return list(range(current_index + direction, target_index + direction, direction))

    def _run_next_step(self) -> None:
        if not self._route:
            if self._pending_target is not None:
                target = self._pending_target
                self._pending_target = None
                self._route = self._build_route(self.currentIndex(), target)
                if self._route:
                    self._run_next_step()
            return

        next_index = self._route.pop(0)
        self._animate_step(next_index, is_final_step=not self._route)

    def _animate_step(self, next_index: int, is_final_step: bool) -> None:
        current_index = self.currentIndex()
        if current_index == next_index:
            self._run_next_step()
            return

        if self.width() <= 1 or self.height() <= 1:
            super().setCurrentIndex(next_index)
            self._run_next_step()
            return

        current_widget = self.widget(current_index)
        target_widget = self.widget(next_index)
        current_pixmap = current_widget.grab()

        self.setUpdatesEnabled(False)
        super().setCurrentIndex(next_index)
        target_pixmap = target_widget.grab()
        super().setCurrentIndex(current_index)
        self.setUpdatesEnabled(True)
        self.update()

        if current_pixmap.isNull() or target_pixmap.isNull():
            super().setCurrentIndex(next_index)
            self._run_next_step()
            return

        direction = 1 if next_index > current_index else -1
        duration = self.FINAL_DURATION_MS if is_final_step else self.INTERMEDIATE_DURATION_MS
        blur_radius = (
            self.FINAL_BLUR_RADIUS if is_final_step else self.INTERMEDIATE_BLUR_RADIUS
        )

        base_rect = self.rect()
        travel = self.SLIDE_DISTANCE if is_final_step else int(self.SLIDE_DISTANCE * 0.8)
        outgoing_end = base_rect.translated(0, -direction * travel)
        incoming_start = base_rect.translated(0, direction * travel)

        if is_final_step:
            outgoing_end = QRect(
                outgoing_end.x() + 3,
                outgoing_end.y(),
                max(1, outgoing_end.width() - 6),
                max(1, outgoing_end.height() - 4),
            )
            incoming_start = QRect(
                incoming_start.x() - 4,
                incoming_start.y(),
                incoming_start.width() + 8,
                incoming_start.height() + 6,
            )

        outgoing = _SnapshotLayer(self, current_pixmap)
        incoming = _SnapshotLayer(self, target_pixmap)
        outgoing.setGeometry(base_rect)
        incoming.setGeometry(incoming_start)

        outgoing.opacity_effect.setOpacity(1.0)
        incoming.opacity_effect.setOpacity(0.0 if is_final_step else 0.12)
        outgoing.blur_effect.setBlurRadius(0.0)
        incoming.blur_effect.setBlurRadius(blur_radius)

        outgoing.show()
        incoming.show()
        outgoing.raise_()
        incoming.raise_()

        group = QParallelAnimationGroup(self)
        easing = (
            QEasingCurve.Type.OutCubic
            if is_final_step
            else QEasingCurve.Type.InOutQuad
        )

        group.addAnimation(
            self._make_animation(
                outgoing,
                b"geometry",
                base_rect,
                outgoing_end,
                duration,
                easing,
            )
        )
        group.addAnimation(
            self._make_animation(
                incoming,
                b"geometry",
                incoming_start,
                base_rect,
                duration,
                easing,
            )
        )
        group.addAnimation(
            self._make_animation(
                outgoing.opacity_effect,
                b"opacity",
                1.0,
                0.0 if is_final_step else 0.18,
                duration,
                easing,
            )
        )
        group.addAnimation(
            self._make_animation(
                incoming.opacity_effect,
                b"opacity",
                0.0 if is_final_step else 0.12,
                1.0,
                duration,
                easing,
            )
        )
        group.addAnimation(
            self._make_animation(
                outgoing.blur_effect,
                b"blurRadius",
                0.0,
                blur_radius,
                duration,
                easing,
            )
        )
        group.addAnimation(
            self._make_animation(
                incoming.blur_effect,
                b"blurRadius",
                blur_radius,
                0.0,
                duration,
                easing,
            )
        )

        self._active_step_target = next_index
        self._transition_layers = [outgoing, incoming]
        self._transition_group = group

        group.finished.connect(self._finish_step)
        group.start()

    def _finish_step(self) -> None:
        target = self._active_step_target

        for layer in self._transition_layers:
            layer.hide()
            layer.deleteLater()

        self._transition_layers = []
        self._transition_group = None
        self._active_step_target = None

        if target is not None and 0 <= target < self.count():
            super().setCurrentIndex(target)

        if self._pending_target is not None:
            pending_target = self._pending_target
            self._pending_target = None
            self._route = self._build_route(self.currentIndex(), pending_target)

        QTimer.singleShot(0, self._run_next_step)

    def resizeEvent(self, event) -> None:
        if self._transition_group is not None:
            self._transition_group.stop()
            target = self._active_step_target

            for layer in self._transition_layers:
                layer.hide()
                layer.deleteLater()

            self._transition_layers = []
            self._transition_group = None
            self._active_step_target = None

            if target is not None and 0 <= target < self.count():
                super().setCurrentIndex(target)

            self._route = []

        super().resizeEvent(event)

    @staticmethod
    def _make_animation(
        target,
        property_name: bytes,
        start_value,
        end_value,
        duration_ms: int,
        easing: QEasingCurve.Type,
    ) -> QPropertyAnimation:
        animation = QPropertyAnimation(target, property_name)
        animation.setStartValue(start_value)
        animation.setEndValue(end_value)
        animation.setDuration(duration_ms)
        animation.setEasingCurve(easing)
        return animation


class LiquidNavButton(QAbstractButton):
    """Navigation button with Apple-like hover drift and color interpolation."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(58)
        self._hover_progress = 0.0
        self._selected = False
        self._hover_animation: QPropertyAnimation | None = None

    def _get_hover_progress(self) -> float:
        return self._hover_progress

    def _set_hover_progress(self, value: float) -> None:
        self._hover_progress = float(value)
        self.update()

    hoverProgress = Property(float, _get_hover_progress, _set_hover_progress)

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self.update()

    def enterEvent(self, event) -> None:
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if not self._selected and self._hover_progress > 0.001:
            alpha = int(18 * self._hover_progress)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, alpha))
            painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 13, 13)

        text_color = QColor(PRIMARY) if self._selected else QColor(TEXT_PRIMARY)
        if not self._selected and self._hover_progress > 0.001:
            accent = QColor(SECONDARY)
            ratio = self._hover_progress * 0.42
            text_color = QColor(
                int(text_color.red() + (accent.red() - text_color.red()) * ratio),
                int(text_color.green() + (accent.green() - text_color.green()) * ratio),
                int(text_color.blue() + (accent.blue() - text_color.blue()) * ratio),
            )

        font = self.font()
        font.setWeight(
            QFont.Weight.Bold if self._selected else QFont.Weight.Normal
        )
        painter.setFont(font)
        painter.setPen(text_color)

        left = 16 + int(4 * self._hover_progress)
        painter.drawText(
            self.rect().adjusted(left, 0, -12, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.text(),
        )

    def _animate_hover(self, end_value: float) -> None:
        if self._hover_animation is not None:
            self._hover_animation.stop()

        animation = QPropertyAnimation(self, b"hoverProgress", self)
        animation.setStartValue(self._hover_progress)
        animation.setEndValue(end_value)
        animation.setDuration(165)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_animation = animation
        animation.finished.connect(self._clear_hover_animation)
        animation.start()

    def _clear_hover_animation(self) -> None:
        self._hover_animation = None


class LiquidBubble(QWidget):
    """Paint the active navigation selection as translucent liquid glass."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 7)
        shadow.setColor(QColor(83, 238, 252, 58))
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(1, 1, -1, -1)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, QColor(171, 201, 255, 236))
        gradient.setColorAt(0.5, QColor(133, 177, 255, 224))
        gradient.setColorAt(1.0, QColor(112, 166, 255, 218))

        painter.setPen(QColor(255, 255, 255, 92))
        painter.setBrush(gradient)
        painter.drawRoundedRect(rect, 15, 15)

        highlight = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        highlight.setColorAt(0.0, QColor(255, 255, 255, 86))
        highlight.setColorAt(0.34, QColor(255, 255, 255, 10))
        highlight.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(highlight)
        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -rect.height() // 2), 13, 13)

        super().paintEvent(event)


class AnimatedSidebar(QWidget):
    """Sidebar whose liquid selection bubble stretches and settles between sections."""

    currentRowChanged = Signal(int)

    CONTENT_MARGIN = 10
    CONTENT_SPACING = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("animatedSidebar")
        self.setFixedWidth(220)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
        )
        self._layout.setSpacing(self.CONTENT_SPACING)

        self._bubble = LiquidBubble(self)
        self._bubble.hide()

        self._buttons: list[LiquidNavButton] = []
        self._current_row = -1
        self._bubble_animation: QPropertyAnimation | None = None

        self._apply_glass_shadow()

    def addItem(self, text: str) -> None:
        index = len(self._buttons)
        button = LiquidNavButton(text, self)
        button.clicked.connect(lambda checked=False, row=index: self.setCurrentRow(row))
        self._buttons.append(button)
        self._layout.addWidget(button)
        self._bubble.lower()

    def addStretch(self) -> None:
        self._layout.addStretch(1)

    def currentRow(self) -> int:
        return self._current_row

    def setCurrentRow(self, row: int, animate: bool = True) -> None:
        if row < 0 or row >= len(self._buttons) or row == self._current_row:
            return

        previous_row = self._current_row
        self._current_row = row

        for index, button in enumerate(self._buttons):
            button.set_selected(index == row)

        step_count = abs(row - previous_row) if previous_row >= 0 else 0
        QTimer.singleShot(
            0,
            lambda: self._move_bubble(
                row,
                animate and previous_row >= 0,
                step_count,
            ),
        )

        self.currentRowChanged.emit(row)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._sync_bubble)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._sync_bubble)

    def _move_bubble(self, row: int, animate: bool, step_count: int) -> None:
        if row < 0 or row >= len(self._buttons):
            return

        target_rect = self._buttons[row].geometry().adjusted(1, 1, -1, -1)
        if target_rect.width() <= 0 or target_rect.height() <= 0:
            QTimer.singleShot(
                0,
                lambda: self._move_bubble(row, animate, step_count),
            )
            return

        self._bubble.show()
        self._bubble.lower()

        if not animate or self._bubble.geometry().isNull():
            self._bubble.setGeometry(target_rect)
            return

        if self._bubble_animation is not None:
            self._bubble_animation.stop()

        start_rect = self._bubble.geometry()
        direction = 1 if target_rect.center().y() > start_rect.center().y() else -1
        distance = abs(target_rect.center().y() - start_rect.center().y())
        stretch = min(34, max(12, int(distance * 0.18)))

        midpoint_y = int((start_rect.center().y() + target_rect.center().y()) / 2)
        mid_rect = QRect(
            min(start_rect.x(), target_rect.x()) - 3,
            midpoint_y - (target_rect.height() + stretch) // 2,
            max(start_rect.width(), target_rect.width()) + 6,
            target_rect.height() + stretch,
        )
        overshoot_rect = target_rect.translated(0, direction * 5)

        duration = min(540, 250 + max(1, step_count) * 48)

        animation = QPropertyAnimation(self._bubble, b"geometry", self)
        animation.setStartValue(start_rect)
        animation.setKeyValueAt(0.42, mid_rect)
        animation.setKeyValueAt(0.82, overshoot_rect)
        animation.setEndValue(target_rect)
        animation.setDuration(duration)
        animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self._bubble_animation = animation
        animation.finished.connect(self._clear_bubble_animation)
        animation.start()

    def _sync_bubble(self) -> None:
        if self._current_row < 0 or self._current_row >= len(self._buttons):
            return

        if self._bubble_animation is not None:
            self._bubble_animation.stop()
            self._bubble_animation = None

        self._bubble.setGeometry(
            self._buttons[self._current_row].geometry().adjusted(1, 1, -1, -1)
        )
        self._bubble.show()
        self._bubble.lower()

    def _clear_bubble_animation(self) -> None:
        self._bubble_animation = None

    def _apply_glass_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(34)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 82))
        self.setGraphicsEffect(shadow)


class LiquidActionButton(QPushButton):
    """Primary action button with soft hover and press depth microanimations."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(24)
        self._shadow.setOffset(0, 8)
        self._shadow.setColor(QColor(83, 238, 252, 66))
        self.setGraphicsEffect(self._shadow)

        self._shadow_animation: QPropertyAnimation | None = None

    def enterEvent(self, event) -> None:
        self._animate_shadow(34.0, 110)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_shadow(24.0, 150)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self._animate_shadow(10.0, 90)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._animate_shadow(32.0 if self.underMouse() else 24.0, 150)
        super().mouseReleaseEvent(event)

    def _animate_shadow(self, radius: float, duration: int) -> None:
        if self._shadow_animation is not None:
            self._shadow_animation.stop()

        animation = QPropertyAnimation(self._shadow, b"blurRadius", self)
        animation.setStartValue(self._shadow.blurRadius())
        animation.setEndValue(radius)
        animation.setDuration(duration)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._shadow_animation = animation
        animation.finished.connect(self._clear_shadow_animation)
        animation.start()

    def _clear_shadow_animation(self) -> None:
        self._shadow_animation = None


class SettingsWindow(QMainWindow):
    SECTION_NAMES = (
        "General",
        "Voice",
        "Microphone",
        "AI",
        "Visualizer",
        "Actions",
        "Knowledge",
        "Advanced",
    )

    def __init__(self, settings_store: SettingsStore) -> None:
        super().__init__()
        self._settings_store = settings_store
        self._settings = settings_store.load()
        self._intro_animation: QPropertyAnimation | None = None

        self.setWindowTitle("Harvis Settings")
        self.resize(1000, 670)
        self.setMinimumSize(840, 560)
        self.setStyleSheet(
            build_app_stylesheet(
                self._settings.ui_scale_percent,
                high_contrast=self._settings.high_contrast,
            )
        )
        self.setWindowOpacity(0.0)

        self._build_ui()
        self.pages.set_reduced_motion(self._settings.reduced_motion)
        self._load_settings_into_controls()

        if self._settings.reduced_motion:
            self.setWindowOpacity(1.0)
        else:
            QTimer.singleShot(0, self._start_intro_animation)

    def _build_ui(self) -> None:
        root = LiquidBackground()
        root.setObjectName("appRoot")

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(26, 24, 26, 24)
        root_layout.setSpacing(18)

        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(2, 0, 2, 0)
        header_layout.setSpacing(3)

        title = QLabel("Harvis")
        title.setObjectName("titleLabel")
        subtitle = QLabel("Personal assistant settings")
        subtitle.setObjectName("mutedLabel")

        self.runtime_status = QLabel("Starting Harvis…")
        self.runtime_status.setObjectName("mutedLabel")
        self.runtime_status.setAccessibleName("Harvis runtime status")

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addWidget(self.runtime_status)
        root_layout.addWidget(header)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        self.sidebar = AnimatedSidebar()
        self.pages = AnimatedStackedWidget()

        page_builders: dict[str, Callable[[], QWidget]] = {
            "General": self._build_general_page,
            "Voice": self._build_voice_page,
            "Microphone": self._build_microphone_page,
            "AI": self._build_ai_page,
            "Visualizer": self._build_visualizer_page,
            "Actions": self._build_actions_page,
            "Knowledge": self._build_knowledge_page,
            "Advanced": self._build_advanced_page,
        }

        for section_name in self.SECTION_NAMES:
            self.sidebar.addItem(section_name)
            page = page_builders[section_name]()
            self.pages.addWidget(self._make_scrollable_page(page))

        self.sidebar.addStretch()
        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndexAnimated)
        self.sidebar.setCurrentRow(0, animate=False)

        content_layout.addWidget(self.sidebar)
        content_layout.addWidget(self.pages, 1)
        root_layout.addLayout(content_layout, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 2, 0, 0)
        footer.addStretch(1)

        self.save_button = LiquidActionButton("Save changes")
        self.save_button.setAccessibleName("Save Harvis settings")
        self.save_button.clicked.connect(self._save_settings)
        footer.addWidget(self.save_button)

        root_layout.addLayout(footer)
        self.setCentralWidget(root)

    def set_runtime_status(self, status: str) -> None:
        if hasattr(self, "runtime_status"):
            self.runtime_status.setText(str(status))

    def apply_accessibility_settings(self) -> None:
        self.setStyleSheet(
            build_app_stylesheet(
                self._settings.ui_scale_percent,
                high_contrast=self._settings.high_contrast,
            )
        )
        self.pages.set_reduced_motion(self._settings.reduced_motion)

    def _start_intro_animation(self) -> None:
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setStartValue(0.0)
        animation.setKeyValueAt(0.72, 1.0)
        animation.setEndValue(1.0)
        animation.setDuration(310)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._intro_animation = animation
        animation.finished.connect(self._clear_intro_animation)
        animation.start()

    def _clear_intro_animation(self) -> None:
        self._intro_animation = None

    def _page_shell(
        self,
        title_text: str,
        description: str,
    ) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(5, 4, 5, 5)
        layout.setSpacing(16)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        title = QLabel(title_text)
        title.setObjectName("sectionTitle")

        description_label = QLabel(description)
        description_label.setObjectName("mutedLabel")
        description_label.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(description_label)
        return page, layout

    @staticmethod
    def _make_scrollable_page(page: QWidget) -> QScrollArea:
        """Keep dense settings pages readable instead of compressing their controls."""

        scroll_area = QScrollArea()
        scroll_area.setObjectName("settingsPageScroll")
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll_area.setWidget(page)
        return scroll_area

    def _build_general_page(self) -> QWidget:
        page, layout = self._page_shell(
            "General",
            "Configure the basic behavior of Harvis.",
        )

        group = self._glass_group("Startup")
        group_layout = QVBoxLayout(group)
        self.start_with_windows = QCheckBox("Start Harvis with Windows")
        group_layout.addWidget(self.start_with_windows)

        layout.addWidget(group)
        layout.addStretch(1)
        return page

    def _build_voice_page(self) -> QWidget:
        page, layout = self._page_shell(
            "Voice",
            "Control how loud Harvis speaks. System volume is managed separately.",
        )

        group = self._glass_group("Speech output")
        form = QFormLayout(group)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.voice_volume = QSlider(Qt.Orientation.Horizontal)
        self.voice_volume.setRange(0, 100)
        self.voice_volume_value = QLabel()
        self.voice_volume.valueChanged.connect(
            lambda value: self.voice_volume_value.setText(f"{value}%")
        )

        volume_row = QWidget()
        volume_layout = QHBoxLayout(volume_row)
        volume_layout.setContentsMargins(0, 0, 0, 0)
        volume_layout.setSpacing(12)
        volume_layout.addWidget(self.voice_volume, 1)
        volume_layout.addWidget(self.voice_volume_value)
        form.addRow("Voice volume", volume_row)

        layout.addWidget(group)
        layout.addStretch(1)
        return page

    def _build_microphone_page(self) -> QWidget:
        page, layout = self._page_shell(
            "Microphone",
            "Select the audio input device Harvis will use when voice recognition is added.",
        )

        group = self._glass_group("Input device")
        form = QFormLayout(group)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.microphone_device = QComboBox()
        self.microphone_device.addItem("System default")
        form.addRow("Microphone", self.microphone_device)

        layout.addWidget(group)
        layout.addStretch(1)
        return page

    def _build_ai_page(self) -> QWidget:
        page, layout = self._page_shell(
            "AI",
            "AI provider integration will handle questions that are not local system actions.",
        )

        group = self._glass_group("Provider")
        form = QFormLayout(group)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.ai_provider = QComboBox()
        self.ai_provider.addItems(("Not configured",))
        form.addRow("AI provider", self.ai_provider)

        note = QLabel(
            "Provider configuration and secure API key storage will be added later."
        )
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)

        layout.addWidget(group)
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _build_visualizer_page(self) -> QWidget:
        page, layout = self._page_shell(
            "Visualizer",
            "Choose whether Harvis displays an audio-reactive visualizer while listening or speaking.",
        )

        group = self._glass_group("Visualizer")
        form = QFormLayout(group)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.visualizer_enabled = QCheckBox("Enable visualizer")
        self.visualizer_type = QComboBox()
        self.visualizer_type.addItems(("Sphere", "Bars"))

        self.visualizer_sensitivity = QSlider(Qt.Orientation.Horizontal)
        self.visualizer_sensitivity.setRange(0, 100)
        self.visualizer_sensitivity_value = QLabel()
        self.visualizer_sensitivity.valueChanged.connect(
            lambda value: self.visualizer_sensitivity_value.setText(f"{value}%")
        )

        sensitivity_row = QWidget()
        sensitivity_layout = QHBoxLayout(sensitivity_row)
        sensitivity_layout.setContentsMargins(0, 0, 0, 0)
        sensitivity_layout.setSpacing(12)
        sensitivity_layout.addWidget(self.visualizer_sensitivity, 1)
        sensitivity_layout.addWidget(self.visualizer_sensitivity_value)

        form.addRow(self.visualizer_enabled)
        form.addRow("Type", self.visualizer_type)
        form.addRow("Sensitivity", sensitivity_row)

        palette_note = QLabel(
            "Sphere: #00072B background, #85B1FF structure, #53EEFC particles.\n"
            "Bars: #00072B background, #85B1FF bars."
        )
        palette_note.setObjectName("mutedLabel")

        layout.addWidget(group)
        layout.addWidget(palette_note)
        layout.addStretch(1)
        return page

    def _build_actions_page(self) -> QWidget:
        page, layout = self._page_shell(
            "Actions",
            "Local actions will allow Harvis to control approved parts of the computer.",
        )

        group = self._glass_group("Initial local actions")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(12)
        group_layout.addWidget(QLabel("Open URLs in the default browser"))
        group_layout.addWidget(QLabel("Change Windows master volume"))

        layout.addWidget(group)
        layout.addStretch(1)
        return page

    def _build_advanced_page(self) -> QWidget:
        page, layout = self._page_shell(
            "Advanced",
            "Developer and diagnostics options will be added as the project grows.",
        )
        layout.addStretch(1)
        return page

    def _build_knowledge_page(self) -> QWidget:
        page, layout = self._page_shell(
            "Knowledge",
            "Manage local memory, named links, routines, and plugins.",
        )
        layout.addStretch(1)
        return page

    def _glass_group(self, title: str) -> QGroupBox:
        group = QGroupBox(title)

        shadow = QGraphicsDropShadowEffect(group)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 64))
        group.setGraphicsEffect(shadow)

        return group

    def _load_settings_into_controls(self) -> None:
        settings = self._settings
        self.start_with_windows.setChecked(settings.start_with_windows)
        self.voice_volume.setValue(settings.voice_volume)
        self.microphone_device.setCurrentText(settings.microphone_device)
        self.visualizer_enabled.setChecked(settings.visualizer_enabled)
        self.visualizer_type.setCurrentText(settings.visualizer_type)
        self.visualizer_sensitivity.setValue(settings.visualizer_sensitivity)
        self.ai_provider.setCurrentText(settings.ai_provider)

    def _save_settings(self) -> None:
        settings = HarvisSettings(
            start_with_windows=self.start_with_windows.isChecked(),
            voice_volume=self.voice_volume.value(),
            microphone_device=self.microphone_device.currentText(),
            visualizer_enabled=self.visualizer_enabled.isChecked(),
            visualizer_type=self.visualizer_type.currentText(),
            visualizer_sensitivity=self.visualizer_sensitivity.value(),
            ai_provider=self.ai_provider.currentText(),
        )
        self._settings_store.save(settings)
        self._settings = settings
        self.statusBar().showMessage("Settings saved", 2500)
