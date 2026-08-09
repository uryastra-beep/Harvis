from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from harvis.config import HarvisSettings, SettingsStore
from harvis.ui.theme import APP_STYLESHEET


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

        self.setWindowTitle("Harvis Settings")
        self.resize(980, 650)
        self.setMinimumSize(820, 540)
        self.setStyleSheet(APP_STYLESHEET)

        self._build_ui()
        self._load_settings_into_controls()

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

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(210)

        self.pages = QStackedWidget()

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
            self.sidebar.addItem(QListWidgetItem(section_name))
            self.pages.addWidget(page_builders[section_name]())

        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

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

    def _page_shell(self, title_text: str, description: str) -> tuple[QWidget, QVBoxLayout]:
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

        note = QLabel("Provider configuration and secure API key storage will be added later.")
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
