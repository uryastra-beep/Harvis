from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from harvis.config import (
    SUPPORTED_ASSISTANT_MODES,
    SUPPORTED_SPEECH_LANGUAGES,
    USER_NAME_MAX_LENGTH,
    HarvisSettings,
)


class OnboardingDialog(QDialog):
    """Small first-launch guide for Harvis's essential choices."""

    def __init__(self, settings: HarvisSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to Harvis")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        title = QLabel("Welcome to Harvis")
        title.setObjectName("sectionTitle")
        title.setAccessibleName("Welcome to Harvis")
        layout.addWidget(title)

        note = QLabel(
            "Choose how Harvis should interact with you. You can change every option later in Settings."
        )
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        form = QFormLayout()
        self.user_name = QLineEdit(settings.user_name)
        self.user_name.setMaxLength(USER_NAME_MAX_LENGTH)
        self.user_name.setAccessibleName("Your name")
        form.addRow("Your name", self.user_name)

        self.language = QComboBox()
        for tag, display_name in SUPPORTED_SPEECH_LANGUAGES.items():
            self.language.addItem(f"{display_name} ({tag})", tag)
        selected_language = self.language.findData(settings.speech_language)
        if selected_language >= 0:
            self.language.setCurrentIndex(selected_language)
        self.language.setAccessibleName("Preferred reply language")
        form.addRow("Language", self.language)

        self.mode = QComboBox()
        self.mode.addItems(SUPPORTED_ASSISTANT_MODES)
        self.mode.setCurrentText(settings.assistant_mode)
        self.mode.setAccessibleName("Interaction mode")
        form.addRow("Mode", self.mode)
        layout.addLayout(form)

        self.proactive = QCheckBox("Enable reminders, scheduled routines, download alerts, and battery alerts")
        self.proactive.setChecked(settings.proactive_enabled)
        self.proactive.setAccessibleName("Enable proactive Harvis")
        layout.addWidget(self.proactive)

        self.local_memory = QCheckBox("Allow explicit, non-secret local memories")
        self.local_memory.setChecked(settings.local_memory_enabled)
        layout.addWidget(self.local_memory)

        self.captions = QCheckBox("Show captions for Harvis responses")
        self.captions.setChecked(settings.captions_enabled)
        layout.addWidget(self.captions)

        privacy = QLabel(
            "Basic local commands continue working without Gemini. Harvis asks for confirmation before sensitive actions."
        )
        privacy.setObjectName("mutedLabel")
        privacy.setWordWrap(True)
        privacy.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(privacy)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Finish setup")
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def apply_to(self, settings: HarvisSettings) -> HarvisSettings:
        settings.user_name = self.user_name.text()
        settings.speech_language = str(self.language.currentData())
        settings.assistant_mode = self.mode.currentText()
        settings.proactive_enabled = self.proactive.isChecked()
        settings.local_memory_enabled = self.local_memory.isChecked()
        settings.captions_enabled = self.captions.isChecked()
        settings.first_run_completed = True
        return settings.normalized()
