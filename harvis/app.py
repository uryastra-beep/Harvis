from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import QApplication, QVBoxLayout

from harvis.assistant import HarvisAssistant
from harvis.config import SettingsStore
from harvis.ui.settings_window import LiquidActionButton, SettingsWindow
from harvis.ui.visualizer_window import VisualizerWindow


class AssistantSignals(QObject):
    """Forward assistant worker callbacks safely into the Qt event loop."""

    status_changed = Signal(str)
    heard = Signal(str)


class HarvisSettingsWindow(SettingsWindow):
    """Settings window with live visualizer preview and assistant integration."""

    def __init__(self, settings_store: SettingsStore) -> None:
        self._visualizer_preview: VisualizerWindow | None = None
        self._assistant: HarvisAssistant | None = None
        super().__init__(settings_store)

    def set_assistant(self, assistant: HarvisAssistant) -> None:
        self._assistant = assistant

    def _build_visualizer_page(self):
        page = super()._build_visualizer_page()
        layout = page.layout()

        self.visualizer_preview_button = LiquidActionButton("Preview visualizer")
        self.visualizer_preview_button.clicked.connect(self._open_visualizer_preview)

        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(
                max(0, layout.count() - 1),
                self.visualizer_preview_button,
                0,
                Qt.AlignmentFlag.AlignLeft,
            )

        return page

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

    def _save_settings(self) -> None:
        super()._save_settings()

        if self._assistant is not None:
            self._assistant.apply_settings(self._settings)

    def closeEvent(self, event) -> None:
        if self._visualizer_preview is not None:
            self._visualizer_preview.close()
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
            assistant_signals.status_changed.connect(
                lambda status: window.statusBar().showMessage(status)
            )
            assistant_signals.heard.connect(
                lambda text: print(f"[Harvis] Heard: {text}")
            )

            assistant = HarvisAssistant(
                settings_store.load(),
                on_heard=assistant_signals.heard.emit,
                on_status=assistant_signals.status_changed.emit,
            )
            window.set_assistant(assistant)
            app.aboutToQuit.connect(assistant.stop)

    window.show()

    if assistant is not None:
        QTimer.singleShot(100, assistant.start)

    return app.exec()
