from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from harvis.ui.theme import PRIMARY, SECONDARY, TERTIARY, TEXT_MUTED, TEXT_PRIMARY


class SilentCommandPopup(QWidget):
    """Small always-on-top text command surface used by Harvis Silent mode."""

    command_submitted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_offset: QPoint | None = None
        self._positioned_once = False
        self._response_text = ""

        self.setWindowTitle("Harvis Silent")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(430)
        self.setMinimumHeight(150)

        self._build_ui()
        self._apply_shadow()

    def _build_ui(self) -> None:
        shell = QWidget(self)
        shell.setObjectName("silentShell")
        shell.setStyleSheet(
            f"""
            QWidget#silentShell {{
                background: rgba(0, 7, 43, 238);
                border: 1px solid {TERTIARY};
                border-radius: 18px;
            }}
            QLabel {{
                color: {TEXT_PRIMARY};
                background: transparent;
            }}
            QLabel#silentModeLabel {{
                color: {SECONDARY};
                font-weight: 700;
                font-size: 13px;
            }}
            QLabel#silentResponse {{
                color: {TEXT_PRIMARY};
                font-size: 13px;
            }}
            QLabel#silentHint {{
                color: {TEXT_MUTED};
                font-size: 11px;
            }}
            QLineEdit {{
                color: {TEXT_PRIMARY};
                background: rgba(255, 255, 255, 14);
                border: 1px solid rgba(133, 177, 255, 105);
                border-radius: 11px;
                padding: 9px 11px;
                selection-background-color: {SECONDARY};
                selection-color: {PRIMARY};
            }}
            QLineEdit:focus {{
                border: 1px solid {TERTIARY};
            }}
            QPushButton {{
                color: {PRIMARY};
                background: {SECONDARY};
                border: none;
                border-radius: 11px;
                padding: 9px 16px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {TERTIARY};
            }}
            """
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.addWidget(shell)

        layout = QVBoxLayout(shell)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)

        header = QHBoxLayout()
        title = QLabel("Harvis · Silent")
        title.setObjectName("silentModeLabel")
        hint = QLabel("Type commands instead of speaking")
        hint.setObjectName("silentHint")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(hint)
        layout.addLayout(header)

        self.response_label = QLabel("Ready when you are.")
        self.response_label.setObjectName("silentResponse")
        self.response_label.setWordWrap(True)
        self.response_label.setMinimumHeight(40)
        layout.addWidget(self.response_label)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Type a command...")
        self.command_input.returnPressed.connect(self._submit_command)
        input_row.addWidget(self.command_input, 1)

        self.send_button = QPushButton("Send")
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.clicked.connect(self._submit_command)
        input_row.addWidget(self.send_button)

        layout.addLayout(input_row)

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.setGraphicsEffect(shadow)

    def _submit_command(self) -> None:
        command = self.command_input.text().strip()
        if not command:
            return

        self.command_input.clear()
        self._response_text = ""
        self.response_label.setText("Working...")
        self.command_submitted.emit(command)

    def set_response(self, text: str) -> None:
        fragment = " ".join(str(text).split()).strip()
        if not fragment:
            return

        if not self._response_text:
            combined = fragment
        elif fragment.startswith(self._response_text):
            combined = fragment
        elif fragment in self._response_text:
            combined = self._response_text
        else:
            combined = f"{self._response_text} {fragment}".strip()

        self._response_text = combined[-700:]
        self.response_label.setText(self._response_text)

    def set_status(self, text: str) -> None:
        value = " ".join(str(text).split()).strip()
        if value and not self._response_text:
            self.response_label.setText(value)

    def focus_command_input(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.command_input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._positioned_once:
            return

        screen = QApplication.primaryScreen()
        if screen is None:
            return

        geometry = screen.availableGeometry()
        x = geometry.center().x() - self.width() // 2
        y = geometry.bottom() - self.height() - 42
        self.move(x, y)
        self._positioned_once = True

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            if not isinstance(child, (QLineEdit, QPushButton)):
                self._drag_offset = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._drag_offset is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


__all__ = ["SilentCommandPopup"]
