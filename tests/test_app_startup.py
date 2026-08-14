from __future__ import annotations

import sys

import pytest


def test_dense_general_settings_keep_controls_readable(tmp_path) -> None:
    from PySide6.QtWidgets import QApplication, QScrollArea

    from harvis.app import HarvisSettingsWindow
    from harvis.config import SettingsStore

    app = QApplication.instance() or QApplication([])
    window = HarvisSettingsWindow(SettingsStore(tmp_path / "settings.json"))
    window.resize(window.minimumSize())
    window.show()
    app.processEvents()

    try:
        assert isinstance(window.pages.widget(0), QScrollArea)
        assert window.assistant_mode.height() >= 34
        assert window.user_name.height() >= 34
        assert window.speech_language.height() >= 34
        assert window.proactive_enabled.isChecked()
        assert window.semantic_file_search.isChecked()
        assert window.visual_memory.isChecked()
        assert window.ui_scale.value() == 100
        assert window.runtime_status.accessibleName() == "Harvis runtime status"
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


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
