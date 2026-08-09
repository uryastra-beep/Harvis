from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from harvis.assistant import HarvisAssistant
from harvis.config import SUPPORTED_SPEECH_LANGUAGES, SettingsStore
from harvis.ui.orb_popup import OrbPopupWindow
from harvis.ui.settings_window import LiquidActionButton, SettingsWindow
from harvis.ui.visualizer_window import VisualizerWindow


class AssistantSignals(QObject):
    """Forward assistant worker callbacks safely into the Qt event loop."""

    status_changed = Signal(str)
    heard = Signal(str)
    response = Signal(str)
    audio_level = Signal(float)
    spectrum = Signal(object)


class HarvisSettingsWindow(SettingsWindow):
    """Settings window with visualizer, language, and assistant integration."""

    def __init__(self, settings_store: SettingsStore) -> None:
        self._visualizer_preview: VisualizerWindow | None = None
        self._live_visualizer: VisualizerWindow | OrbPopupWindow | None = None
        self._assistant: HarvisAssistant | None = None
        super().__init__(settings_store)

    def set_assistant(self, assistant: HarvisAssistant) -> None:
        self._assistant = assistant

    def _build_general_page(self):
        page = super()._build_general_page()
        layout = page.layout()

        language_group = self._glass_group("Language")
        language_form = QFormLayout(language_group)
        language_form.setHorizontalSpacing(18)
        language_form.setVerticalSpacing(12)

        self.speech_language = QComboBox()
        for language_tag, display_name in SUPPORTED_SPEECH_LANGUAGES.items():
            self.speech_language.addItem(
                f"{display_name} ({language_tag})",
                language_tag,
            )

        language_form.addRow("Preferred language", self.speech_language)

        language_note = QLabel(
            "Gemini Live can understand multiple languages. "
            "This setting controls Harvis's preferred response language."
        )
        language_note.setObjectName("mutedLabel")
        language_note.setWordWrap(True)
        language_form.addRow(language_note)

        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(max(0, layout.count() - 1), language_group)

        return page

    def _build_ai_page(self):
        page, layout = self._page_shell(
            "AI",
            "Configure the cloud intelligence provider used for live conversation.",
        )

        group = self._glass_group("Provider")
        form = QFormLayout(group)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.ai_provider = QComboBox()
        self.ai_provider.addItems(("Gemini Live",))
        form.addRow("AI provider", self.ai_provider)

        note = QLabel(
            "Gemini Live reads the API key from the GEMINI_API_KEY environment variable. "
            "The key is never stored in Harvis settings."
        )
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)

        layout.addWidget(group)
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _build_visualizer_page(self):
        page = super()._build_visualizer_page()
        layout = page.layout()

        self.visualizer_preview_button = LiquidActionButton("Preview visualizer")
        self.visualizer_preview_button.clicked.connect(self._open_visualizer_preview)

        live_note = QLabel(
            "When enabled, the live visualizer reacts to Harvis's actual Gemini voice audio. "
            "Sphere mode appears as a small transparent always-on-top orb that can be dragged anywhere."
        )
        live_note.setObjectName("mutedLabel")
        live_note.setWordWrap(True)

        if isinstance(layout, QVBoxLayout):
            insertion_index = max(0, layout.count() - 1)
            layout.insertWidget(insertion_index, live_note)
            layout.insertWidget(
                insertion_index + 1,
                self.visualizer_preview_button,
                0,
                Qt.AlignmentFlag.AlignLeft,
            )

        return page

    def _load_settings_into_controls(self) -> None:
        super()._load_settings_into_controls()

        if hasattr(self, "speech_language"):
            index = self.speech_language.findData(self._settings.speech_language)
            if index >= 0:
                self.speech_language.setCurrentIndex(index)

    def _open_visualizer_preview(self) -> None:
        if self._visualizer_preview is not None:
            self._visualizer_preview.close()
            self._visualizer_preview.deleteLater()

        preview = VisualizerWindow(
            visualizer_type=self.visualizer_type.currentText(),
            sensitivity=self.visualizer_sensitivity.value(),
            demo_mode=True,
        )
        preview.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        preview.destroyed.connect(self._clear_visualizer_preview)
        self._visualizer_preview = preview
        preview.show()
        preview.raise_()
        preview.activateWindow()

    def _clear_visualizer_preview(self, *args) -> None:
        self._visualizer_preview = None

    def _clear_live_visualizer(self, *args) -> None:
        self._live_visualizer = None

    def _live_visualizer_matches_settings(self) -> bool:
        if self._live_visualizer is None:
            return False

        wants_sphere = self._settings.visualizer_type.strip().lower() == "sphere"
        return (
            wants_sphere and isinstance(self._live_visualizer, OrbPopupWindow)
        ) or (
            not wants_sphere and isinstance(self._live_visualizer, VisualizerWindow)
        )

    def _create_live_visualizer(self) -> VisualizerWindow | OrbPopupWindow:
        if self._settings.visualizer_type.strip().lower() == "sphere":
            visualizer: VisualizerWindow | OrbPopupWindow = OrbPopupWindow(
                sensitivity=self._settings.visualizer_sensitivity,
                demo_mode=False,
            )
        else:
            visualizer = VisualizerWindow(
                visualizer_type="Bars",
                sensitivity=self._settings.visualizer_sensitivity,
                demo_mode=False,
            )

        visualizer.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        visualizer.destroyed.connect(self._clear_live_visualizer)
        return visualizer

    def sync_live_visualizer(self) -> None:
        if self._assistant is None or not self._settings.visualizer_enabled:
            if self._live_visualizer is not None:
                self._live_visualizer.close()
            return

        if not self._live_visualizer_matches_settings():
            if self._live_visualizer is not None:
                self._live_visualizer.close()
            self._live_visualizer = self._create_live_visualizer()

        self._live_visualizer.set_sensitivity(
            self._settings.visualizer_sensitivity
        )
        self._live_visualizer.set_demo_mode(False)
        self._live_visualizer.show()
        self._live_visualizer.raise_()

    def set_live_audio_level(self, level: float) -> None:
        if self._live_visualizer is not None:
            self._live_visualizer.set_audio_level(level)

    def set_live_spectrum(self, spectrum) -> None:
        if self._live_visualizer is not None:
            self._live_visualizer.set_spectrum(spectrum)

    def _save_settings(self) -> None:
        selected_language = self.speech_language.currentData()
        super()._save_settings()

        if isinstance(selected_language, str) and selected_language:
            self._settings.speech_language = selected_language
            self._settings_store.save(self._settings)

        if self._assistant is not None:
            self._assistant.apply_settings(self._settings)

        self.sync_live_visualizer()

    def closeEvent(self, event) -> None:
        if self._visualizer_preview is not None:
            self._visualizer_preview.close()
        if self._live_visualizer is not None:
            self._live_visualizer.close()
        super().closeEvent(event)


def _parse_runtime_options() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--visualizer-preview",
        choices=("sphere", "bars"),
        default=None,
    )
    parser.add_argument(
        "--visualizer-sensitivity",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--no-voice",
        action="store_true",
    )
    options, remaining_args = parser.parse_known_args(sys.argv[1:])
    return options, [sys.argv[0], *remaining_args]


def main() -> int:
    options, qt_args = _parse_runtime_options()

    app = QApplication(qt_args)
    app.setApplicationName("Harvis")
    app.setOrganizationName("Harvis")

    settings_store = SettingsStore()
    assistant: HarvisAssistant | None = None
    assistant_signals: AssistantSignals | None = None

    if options.visualizer_preview is not None:
        settings = settings_store.load()
        sensitivity = (
            settings.visualizer_sensitivity
            if options.visualizer_sensitivity is None
            else max(0, min(100, options.visualizer_sensitivity))
        )
        window = VisualizerWindow(
            visualizer_type=options.visualizer_preview,
            sensitivity=sensitivity,
            demo_mode=True,
        )
    else:
        window = HarvisSettingsWindow(settings_store)

        if not options.no_voice:
            assistant_signals = AssistantSignals()

            def show_status(status: str) -> None:
                print(f"[Harvis] {status}", flush=True)
                window.statusBar().showMessage(status)

            def show_heard(text: str) -> None:
                print(f"[Harvis] Heard: {text}", flush=True)

            def show_response(text: str) -> None:
                print(f"[Harvis] Response: {text}", flush=True)

            assistant_signals.status_changed.connect(show_status)
            assistant_signals.heard.connect(show_heard)
            assistant_signals.response.connect(show_response)
            assistant_signals.audio_level.connect(window.set_live_audio_level)
            assistant_signals.spectrum.connect(window.set_live_spectrum)

            assistant = HarvisAssistant(
                settings_store.load(),
                on_heard=assistant_signals.heard.emit,
                on_response=assistant_signals.response.emit,
                on_audio_level=assistant_signals.audio_level.emit,
                on_spectrum=assistant_signals.spectrum.emit,
                on_status=assistant_signals.status_changed.emit,
            )
            window.set_assistant(assistant)
            app.aboutToQuit.connect(assistant.stop)

    window.show()

    if assistant is not None:
        window.sync_live_visualizer()
        print("[Harvis] Gemini Live runtime scheduled to start.", flush=True)
        QTimer.singleShot(300, assistant.start)

    return app.exec()
