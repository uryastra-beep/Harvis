from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from harvis.config import SettingsStore
from harvis.ui.settings_window import SettingsWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Harvis")
    app.setOrganizationName("Harvis")

    settings_store = SettingsStore()
    window = SettingsWindow(settings_store)
    window.show()

    return app.exec()
