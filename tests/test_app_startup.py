from __future__ import annotations

import sys

import pytest


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="This regression covers the packaged Windows Qt startup path.",
)
def test_settings_window_initializes_qt_before_child_signals(tmp_path) -> None:
    from PySide6.QtWidgets import QApplication

    from harvis.app import HarvisSettingsWindow
    from harvis.config import SettingsStore

    app = QApplication.instance() or QApplication([])
    window = HarvisSettingsWindow(SettingsStore(tmp_path / "settings.json"))

    try:
        assert window._update_signals.parent() is window
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
