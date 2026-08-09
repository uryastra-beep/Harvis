from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGraphicsBlurEffect,
    QGraphicsOpacityEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from harvis.config import HarvisSettings, SettingsStore
from harvis.ui.theme import (
    APP_STYLESHEET,
    PRIMARY,
    SECONDARY,
    SURFACE,
    SURFACE_HOVER,
    TERTIARY,
    TEXT_PRIMARY,
)


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
    """Move through every intermediate page with fast motion-blurred transitions."""

    INTERMEDIATE_DURATION_MS = 88
    FINAL_DURATION_MS = 180
    INTERMEDIATE_BLUR_RADIUS = 12.0
    FINAL_BLUR_RADIUS = 8.0
    SLIDE_DISTANCE = 56

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._transition_group: QParallelAnimationGroup | None = None
        self._transition_layers: list[_SnapshotLayer] = []
        self._route: list[int] = []
        self._active_step_target: int | None = None
        self._pending_target: int | None = None

    def setCurrentIndexAnimated(self, index: int) -> None:
        if index < 0 or index >= self.count():
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
        is_final_step = not self._route
        self._animate_step(next_index, is_final_step)

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
            self.FINAL_BLUR_RADIUS
            if is_final_step
            else self.INTERMEDIATE_BLUR_RADIUS
        )

        base_rect = self.rect()
        outgoing_end = base_rect.translated(0, -direction * self.SLIDE_DISTANCE)
        incoming_start = base_rect.translated(0, direction * self.SLIDE_DISTANCE)

        outgoing = _SnapshotLayer(self, current_pixmap)
        incoming = _SnapshotLayer(self, target_pixmap)
        outgoing.setGeometry(base_rect)
        incoming.setGeometry(incoming_start)

        outgoing.opacity_effect.setOpacity(1.0)
        incoming.opacity_effect.setOpacity(0.0)
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
                0.16 if not is_final_step else 0.0,
                duration,
                easing,
            )
        )
        group.addAnimation(
            self._make_animation(
                incoming.opacity_effect,
                b"opacity",
                0.15 if not is_final_step else 0.0,
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


class AnimatedSidebar(QFrame):
    """Sidebar with a rounded secondary-color bubble that glides between sections."""

    currentRowChanged = Signal(int)

    BUTTON_HEIGHT = 58
    CONTENT_MARGIN = 10
    CONTENT_SPACING = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("animatedSidebar")
        self.setFixedWidth(210)
        self.setStyleSheet(
            f"""
            QFrame#animatedSidebar {{
                background-color: {SURFACE};
                border: 1px solid {TERTIARY};
                border-radius: 12px;
            }}
            """
        )

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
        )
        self._layout.setSpacing(self.CONTENT_SPACING)

        self._bubble = QFrame(self)
        self._bubble.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self._bubble.setStyleSheet(
            f"background-color: {SECONDARY}; border: none; border-radius: 8px;"
        )
        self._bubble.hide()

        self._buttons: list[QPushButton] = []
        self._current_row = -1
        self._bubble_animation: QPropertyAnimation | None = None

    def addItem(self, text: str) -> None:
        index = len(self._buttons)

        button = QPushButton(text, self)
        button.setFixedHeight(self.BUTTON_HEIGHT)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda checked=False, row=index: self.setCurrentRow(row))

        self._buttons.append(button)
        self._layout.addWidget(button)
        self._refresh_button_styles()

        self._bubble.lower()

    def addStretch(self) -> None:
        self._layout.addStretch(1)

    def currentRow(self) -> int:
        return self._current_row

    def setCurrentRow(self, row: int, animate: bool = True) -> None:
        if row < 0 or row >= len(self._buttons):
            return

        if row == self._current_row:
            return

        previous_row = self._current_row
        self._current_row = row
        self._refresh_button_styles()

        step_count = abs(row - previous_row) if previous_row >= 0 else 0
        QTimer.singleShot(
            0,
            lambda: self._move_bubble(row, animate and previous_row >= 0, step_count),
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

        target_rect = self._buttons[row].geometry()

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

        duration = min(560, 140 + max(1, step_count) * 68)

        animation = QPropertyAnimation(self._bubble, b"geometry", self)
        animation.setStartValue(self._bubble.geometry())
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

        self._bubble.setGeometry(self._buttons[self._current_row].geometry())
        self._bubble.show()
        self._bubble.lower()

    def _clear_bubble_animation(self) -> None:
        self._bubble_animation = None

    def _refresh_button_styles(self) -> None:
        for index, button in enumerate(self._buttons):
            is_selected = index == self._current_row
            color = PRIMARY if is_selected else TEXT_PRIMARY
            weight = 700 if is_selected else 400
            hover_background = "transparent" if is_selected else SURFACE_HOVER

            button.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: transparent;
                    color: {color};
                    border: none;
                    border-radius: 8px;
                    padding: 10px 12px;
                    text-align: left;
                    font-weight: {weight};
                }}
                QPushButton:hover {{
                    background-color: {hover_background};
                }}
                QPushButton:pressed {{
                    background-color: transparent;
                }}
                """
            )


class SettingsWindow(QMainWindow):
    SECTION_NAMES = (
        "General",
        "Voice",
        "Microphone",
        "AI",
        "Visualizer",
        "Actions",
        "Advanced",
    )

    def __init__(self, settings_store: SettingsStore) -> None:
        super().__init__()
        self._settings_store = settings_store
        self._settings = settings_store.load()
        self._intro_animation: QPropertyAnimation | None = None

        self.setWindowTitle("Harvis Settings")
        self.resize(980, 650)
        self.setMinimumSize(820, 540)
        self.setStyleSheet(APP_STYLESHEET)
        self.setWindowOpacity(0.0)

        self._build_ui()
        self._load_settings_into_controls()

        QTimer.singleShot(0, self._start_intro_animation)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(24, 22, 24, 22)
        root_layout.setSpacing(18)

        title = QLabel("Harvis")
        title.setObjectName("titleLabel")
        subtitle = QLabel("Personal assistant settings")
        subtitle.setObjectName("mutedLabel")

        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(18)

        self.sidebar = AnimatedSidebar()
        self.pages = AnimatedStackedWidget()

        page_builders: dict[str, Callable[[], QWidget]] = {
            "General": self._build_general_page,
            "Voice": self._build_voice_page,
            "Microphone": self._build_microphone_page,
            "AI": self._build_ai_page,
            "Visualizer": self._build_visualizer_page,
            "Actions": self._build_actions_page,
            "Advanced": self._build_advanced_page,
        }

        for section_name in self.SECTION_NAMES:
            self.sidebar.addItem(section_name)
            self.pages.addWidget(page_builders[section_name]())

        self.sidebar.addStretch()
        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndexAnimated)
        self.sidebar.setCurrentRow(0, animate=False)

        content_layout.addWidget(self.sidebar)
        content_layout.addWidget(self.pages, 1)
        root_layout.addLayout(content_layout, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.save_button = QPushButton("Save changes")
        self.save_button.clicked.connect(self._save_settings)
        footer.addWidget(self.save_button)
        root_layout.addLayout(footer)

        self.setCentralWidget(root)

    def _start_intro_animation(self) -> None:
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(220)
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
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(14)

        title = QLabel(title_text)
        title.setObjectName("sectionTitle")
        description_label = QLabel(description)
        description_label.setObjectName("mutedLabel")
        description_label.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(description_label)
        return page, layout

    def _build_general_page(self) -> QWidget:
        page, layout = self._page_shell(
            "General",
            "Configure the basic behavior of Harvis.",
        )

        group = QGroupBox("Startup")
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

        group = QGroupBox("Speech output")
        form = QFormLayout(group)

        self.voice_volume = QSlider(Qt.Orientation.Horizontal)
        self.voice_volume.setRange(0, 100)
        self.voice_volume_value = QLabel()
        self.voice_volume.valueChanged.connect(
            lambda value: self.voice_volume_value.setText(f"{value}%")
        )

        volume_row = QWidget()
        volume_layout = QHBoxLayout(volume_row)
        volume_layout.setContentsMargins(0, 0, 0, 0)
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

        group = QGroupBox("Input device")
        form = QFormLayout(group)
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

        group = QGroupBox("Provider")
        form = QFormLayout(group)
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

        group = QGroupBox("Visualizer")
        form = QFormLayout(group)

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

        group = QGroupBox("Initial local actions")
        group_layout = QVBoxLayout(group)
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
