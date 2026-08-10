from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from harvis.actions.keyboard_control import set_ai_watermark_enabled
from harvis.assistant import HarvisAssistant
from harvis.config import (
    SUPPORTED_ASSISTANT_MODES,
    SUPPORTED_SPEECH_LANGUAGES,
    SettingsStore,
    USER_NAME_MAX_LENGTH,
)
from harvis.credentials import (
    CredentialStoreError,
    get_gemini_api_key,
    save_gemini_api_key,
    sync_gemini_api_key_environment,
)
from harvis.single_instance import SingleInstanceCoordinator
from harvis.ui.orb_popup import OrbPopupWindow
from harvis.ui.settings_window import LiquidActionButton, SettingsWindow
from harvis.ui.silent_popup import SilentCommandPopup
from harvis.ui.visualizer_window import VisualizerWindow


class AssistantSignals(QObject):
    """Forward assistant worker callbacks safely into the Qt event loop."""

    status_changed = Signal(str)
    heard = Signal(str)
    response = Signal(str)
    audio_level = Signal(float)
    spectrum = Signal(object)
    shutdown_requested = Signal()


class HarvisSettingsWindow(SettingsWindow):
    """Settings window with interaction mode and assistant integration."""

    def __init__(self, settings_store: SettingsStore) -> None:
        self._visualizer_preview: VisualizerWindow | None = None
        self._live_visualizer: (
            VisualizerWindow | OrbPopupWindow | SilentCommandPopup | None
        ) = None
        self._assistant: HarvisAssistant | None = None
        super().__init__(settings_store)
        set_ai_watermark_enabled(self._settings.ai_watermark_enabled)

    def set_assistant(self, assistant: HarvisAssistant) -> None:
        self._assistant = assistant

    def _build_general_page(self):
        page = super()._build_general_page()
        layout = page.layout()

        mode_group = self._glass_group("Interaction mode")
        mode_form = QFormLayout(mode_group)
        mode_form.setHorizontalSpacing(18)
        mode_form.setVerticalSpacing(12)

        self.assistant_mode = QComboBox()
        self.assistant_mode.addItems(SUPPORTED_ASSISTANT_MODES)
        mode_form.addRow("Mode", self.assistant_mode)

        mode_note = QLabel(
            "Speaking uses the microphone and voice output. Silent disables microphone and speaker use, "
            "replacing the live visualizer with a compact text command popup."
        )
        mode_note.setObjectName("mutedLabel")
        mode_note.setWordWrap(True)
        mode_form.addRow(mode_note)

        personalization_group = self._glass_group("Personalization")
        personalization_form = QFormLayout(personalization_group)
        personalization_form.setHorizontalSpacing(18)
        personalization_form.setVerticalSpacing(12)

        self.user_name = QLineEdit()
        self.user_name.setMaxLength(USER_NAME_MAX_LENGTH)
        self.user_name.setPlaceholderText("Your name")
        personalization_form.addRow("Your name", self.user_name)

        self.speech_language = QComboBox()
        for language_tag, display_name in SUPPORTED_SPEECH_LANGUAGES.items():
            self.speech_language.addItem(
                f"{display_name} ({language_tag})",
                language_tag,
            )

        personalization_form.addRow("Preferred language", self.speech_language)

        personalization_note = QLabel(
            "Harvis uses your name for its startup greeting and the language setting for its preferred replies."
        )
        personalization_note.setObjectName("mutedLabel")
        personalization_note.setWordWrap(True)
        personalization_form.addRow(personalization_note)

        if isinstance(layout, QVBoxLayout):
            insertion_index = max(0, layout.count() - 1)
            layout.insertWidget(insertion_index, mode_group)
            layout.insertWidget(insertion_index + 1, personalization_group)

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

        self.ai_watermark = QComboBox()
        self.ai_watermark.addItems(("On", "Off"))
        form.addRow("AI watermark", self.ai_watermark)

        self.gemini_api_key = QLineEdit()
        self.gemini_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_api_key.setClearButtonEnabled(True)
        form.addRow("Gemini API key", self.gemini_api_key)

        self.gemini_api_key_status = QLabel()
        self.gemini_api_key_status.setObjectName("mutedLabel")
        self.gemini_api_key_status.setWordWrap(True)
        form.addRow(self.gemini_api_key_status)
        self._refresh_gemini_api_key_status()

        watermark_note = QLabel(
            "When AI watermark is On, every text entry Harvis types starts with #G6m2i9 to identify AI-written text."
        )
        watermark_note.setObjectName("mutedLabel")
        watermark_note.setWordWrap(True)

        note = QLabel(
            "Paste a key and choose Save changes. On Windows, Harvis stores it in Windows Credential Manager. "
            "On Linux, Harvis stores it in a user-only secrets file. The key is never written to settings.json "
            "or the Git repository. Leave the field blank to keep the currently saved key."
        )
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)

        layout.addWidget(group)
        layout.addWidget(watermark_note)
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _refresh_gemini_api_key_status(self) -> None:
        if not hasattr(self, "gemini_api_key"):
            return

        try:
            configured = bool(get_gemini_api_key())
        except CredentialStoreError:
            configured = False

        if configured:
            self.gemini_api_key.setPlaceholderText(
                "API key saved - paste a new key here to replace it"
            )
            self.gemini_api_key_status.setText("API key status: configured")
        else:
            self.gemini_api_key.setPlaceholderText("Paste your Gemini API key")
            self.gemini_api_key_status.setText("API key status: not configured")

    def _build_visualizer_page(self):
        page = super()._build_visualizer_page()
        layout = page.layout()

        self.visualizer_preview_button = LiquidActionButton("Preview visualizer")
        self.visualizer_preview_button.clicked.connect(self._open_visualizer_preview)

        live_note = QLabel(
            "When enabled in Speaking mode, the live visualizer reacts to Harvis's actual Gemini voice audio. "
            "Sphere mode appears as a small transparent always-on-top orb that can be dragged anywhere. "
            "Silent mode replaces the visualizer with the text command popup."
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

        if hasattr(self, "assistant_mode"):
            self.assistant_mode.setCurrentText(self._settings.assistant_mode)

        if hasattr(self, "user_name"):
            self.user_name.setText(self._settings.user_name)

        if hasattr(self, "speech_language"):
            index = self.speech_language.findData(self._settings.speech_language)
            if index >= 0:
                self.speech_language.setCurrentIndex(index)

        if hasattr(self, "ai_watermark"):
            self.ai_watermark.setCurrentText(
                "On" if self._settings.ai_watermark_enabled else "Off"
            )

        self._refresh_gemini_api_key_status()

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
        preview.destroyed.connect(
            lambda *args, current=preview: self._clear_visualizer_preview(current)
        )
        self._visualizer_preview = preview
        preview.show()
        preview.raise_()
        preview.activateWindow()

    def _clear_visualizer_preview(self, preview=None) -> None:
        if preview is None or self._visualizer_preview is preview:
            self._visualizer_preview = None

    def _clear_live_visualizer(self, visualizer=None) -> None:
        if visualizer is None or self._live_visualizer is visualizer:
            self._live_visualizer = None

    def _live_visualizer_matches_settings(self) -> bool:
        if self._live_visualizer is None:
            return False

        if self._settings.assistant_mode == "Silent":
            return isinstance(self._live_visualizer, SilentCommandPopup)

        wants_sphere = self._settings.visualizer_type.strip().lower() == "sphere"
        return (
            wants_sphere and isinstance(self._live_visualizer, OrbPopupWindow)
        ) or (
            not wants_sphere and isinstance(self._live_visualizer, VisualizerWindow)
        )

    def _create_live_visualizer(
        self,
    ) -> VisualizerWindow | OrbPopupWindow | SilentCommandPopup:
        if self._settings.assistant_mode == "Silent":
            popup = SilentCommandPopup()
            popup.command_submitted.connect(self._submit_silent_command)
            popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            popup.destroyed.connect(
                lambda *args, current=popup: self._clear_live_visualizer(current)
            )
            return popup

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
        visualizer.destroyed.connect(
            lambda *args, current=visualizer: self._clear_live_visualizer(current)
        )
        return visualizer

    def sync_live_visualizer(self) -> None:
        if self._assistant is None:
            if self._live_visualizer is not None:
                self._live_visualizer.close()
            return

        if (
            self._settings.assistant_mode != "Silent"
            and not self._settings.visualizer_enabled
        ):
            if self._live_visualizer is not None:
                self._live_visualizer.close()
            return

        if not self._live_visualizer_matches_settings():
            if self._live_visualizer is not None:
                self._live_visualizer.close()
            self._live_visualizer = self._create_live_visualizer()

        if isinstance(self._live_visualizer, SilentCommandPopup):
            self._live_visualizer.show()
            self._live_visualizer.raise_()
            self._live_visualizer.focus_command_input()
            return

        self._live_visualizer.set_sensitivity(
            self._settings.visualizer_sensitivity
        )
        self._live_visualizer.set_demo_mode(False)
        self._live_visualizer.show()
        self._live_visualizer.raise_()

    def _submit_silent_command(self, text: str) -> None:
        popup = self._live_visualizer
        if self._assistant is None or not isinstance(popup, SilentCommandPopup):
            return

        try:
            self._assistant.send_text_command(text)
        except Exception as exc:
            popup.set_response(f"Could not send command: {exc}")

    def set_silent_response(self, text: str) -> None:
        if isinstance(self._live_visualizer, SilentCommandPopup):
            self._live_visualizer.set_response(text)

    def set_silent_status(self, status: str) -> None:
        if isinstance(self._live_visualizer, SilentCommandPopup):
            self._live_visualizer.set_status(status)

    def focus_silent_popup(self) -> None:
        if isinstance(self._live_visualizer, SilentCommandPopup):
            self._live_visualizer.focus_command_input()

    def set_live_audio_level(self, level: float) -> None:
        if isinstance(self._live_visualizer, (OrbPopupWindow, VisualizerWindow)):
            self._live_visualizer.set_audio_level(level)

    def set_live_spectrum(self, spectrum) -> None:
        if isinstance(self._live_visualizer, (OrbPopupWindow, VisualizerWindow)):
            self._live_visualizer.set_spectrum(spectrum)

    def _save_settings(self) -> None:
        selected_user_name = self.user_name.text()
        selected_language = self.speech_language.currentData()
        selected_mode = self.assistant_mode.currentText()
        selected_ai_watermark = self.ai_watermark.currentText() == "On"
        pending_api_key = self.gemini_api_key.text().strip()
        api_key_changed = False

        if pending_api_key:
            try:
                save_gemini_api_key(pending_api_key)
            except (CredentialStoreError, ValueError) as exc:
                self.statusBar().showMessage(
                    f"Could not save Gemini API key: {exc}",
                    6000,
                )
                return
            api_key_changed = True
            self.gemini_api_key.clear()
            self._refresh_gemini_api_key_status()

        super()._save_settings()

        self._settings.user_name = selected_user_name
        self._settings.assistant_mode = selected_mode
        self._settings.ai_watermark_enabled = selected_ai_watermark
        if isinstance(selected_language, str) and selected_language:
            self._settings.speech_language = selected_language
        self._settings_store.save(self._settings)
        self.user_name.setText(self._settings.user_name)
        self.assistant_mode.setCurrentText(self._settings.assistant_mode)
        self.ai_watermark.setCurrentText(
            "On" if self._settings.ai_watermark_enabled else "Off"
        )
        set_ai_watermark_enabled(self._settings.ai_watermark_enabled)

        if self._assistant is not None:
            if api_key_changed:
                self._assistant.stop()
            self._assistant.apply_settings(self._settings)
            if api_key_changed:
                self._assistant.start()

        self.sync_live_visualizer()

        if api_key_changed:
            self.statusBar().showMessage(
                "Settings saved. Gemini Live restarted with the saved API key.",
                4000,
            )

    def closeEvent(self, event) -> None:
        if self._visualizer_preview is not None:
            self._visualizer_preview.close()
        if self._live_visualizer is not None:
            self._live_visualizer.close()
        if self._assistant is not None:
            self._assistant.stop()
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


def _activate_window(window) -> None:
    if window.isMinimized():
        window.showNormal()
    else:
        window.show()
    window.raise_()
    window.activateWindow()
    if hasattr(window, "focus_silent_popup"):
        window.focus_silent_popup()


def main() -> int:
    options, qt_args = _parse_runtime_options()

    app = QApplication(qt_args)
    app.setApplicationName("Harvis")
    app.setOrganizationName("Harvis")
    app.setQuitOnLastWindowClosed(True)

    instance_coordinator: SingleInstanceCoordinator | None = None
    if options.visualizer_preview is None:
        instance_coordinator = SingleInstanceCoordinator(parent=app)
        try:
            if not instance_coordinator.acquire_or_activate_existing():
                return 0
        except RuntimeError as exc:
            print(f"[Harvis] Single-instance startup failed: {exc}", flush=True)
            return 1
        app.aboutToQuit.connect(instance_coordinator.close)

    sync_gemini_api_key_environment()

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
                window.set_silent_status(status)

            def show_heard(text: str) -> None:
                print(f"[Harvis] Heard: {text}", flush=True)

            def show_response(text: str) -> None:
                print(f"[Harvis] Response: {text}", flush=True)
                window.set_silent_response(text)

            def request_shutdown() -> None:
                print("[Harvis] Voice shutdown requested.", flush=True)
                window.statusBar().showMessage("Shutting down Harvis")
                QTimer.singleShot(250, app.quit)

            assistant_signals.status_changed.connect(show_status)
            assistant_signals.heard.connect(show_heard)
            assistant_signals.response.connect(show_response)
            assistant_signals.audio_level.connect(window.set_live_audio_level)
            assistant_signals.spectrum.connect(window.set_live_spectrum)
            assistant_signals.shutdown_requested.connect(request_shutdown)

            assistant = HarvisAssistant(
                settings_store.load(),
                on_heard=assistant_signals.heard.emit,
                on_response=assistant_signals.response.emit,
                on_audio_level=assistant_signals.audio_level.emit,
                on_spectrum=assistant_signals.spectrum.emit,
                on_status=assistant_signals.status_changed.emit,
                on_shutdown_requested=assistant_signals.shutdown_requested.emit,
            )
            window.set_assistant(assistant)
            app.aboutToQuit.connect(assistant.stop)

    if instance_coordinator is not None:
        instance_coordinator.activation_requested.connect(
            lambda: _activate_window(window)
        )

    window.show()

    if assistant is not None:
        window.sync_live_visualizer()
        print("[Harvis] Gemini Live runtime scheduled to start.", flush=True)
        QTimer.singleShot(300, assistant.start)

    return app.exec()
