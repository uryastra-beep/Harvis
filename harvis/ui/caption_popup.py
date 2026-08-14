from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class CaptionPopup(QWidget):
    """Keyboard- and screen-reader-friendly transient response captions."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setObjectName("captionPopup")
        self.setMinimumWidth(420)
        self.setMaximumWidth(760)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setAccessibleName("Harvis response caption")
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.label)

        self.setStyleSheet(
            "QWidget#captionPopup { background: rgba(0, 7, 43, 235); "
            "border: 2px solid #53EEFC; border-radius: 16px; } "
            "QLabel { color: #FFFFFF; font: 12pt 'Segoe UI'; }"
        )
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_caption(self, text: str) -> None:
        clean_text = str(text).strip()
        if not clean_text:
            return
        self.label.setText(clean_text)
        self.adjustSize()
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            self.move(
                available.center().x() - self.width() // 2,
                available.bottom() - self.height() - 42,
            )
        self.show()
        self.raise_()
        self._hide_timer.start(10_000)
