from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

DEFAULT_SERVER_NAME = "HarvisDesktopAssistant"
CONNECT_TIMEOUT_MS = 220


class SingleInstanceCoordinator(QObject):
    """Keep one Harvis UI process alive and reactivate it on later launches."""

    activation_requested = Signal()

    def __init__(
        self,
        server_name: str = DEFAULT_SERVER_NAME,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._server_name = str(server_name).strip() or DEFAULT_SERVER_NAME
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._accept_pending_connections)
        self._owns_server = False

    @property
    def owns_server(self) -> bool:
        return self._owns_server

    def acquire_or_activate_existing(self) -> bool:
        """Return True for the primary instance, otherwise activate the existing one."""

        if self._notify_existing_instance():
            return False

        # Unix local sockets can leave a stale endpoint after an abnormal exit.
        # Removing it is safe here because the connection probe above already failed.
        QLocalServer.removeServer(self._server_name)

        if self._server.listen(self._server_name):
            self._owns_server = True
            return True

        # Another launch may have won the race between our probe and listen call.
        if self._notify_existing_instance():
            return False

        raise RuntimeError(
            f"Harvis could not create its single-instance endpoint: {self._server.errorString()}"
        )

    def close(self) -> None:
        if self._owns_server:
            self._server.close()
            QLocalServer.removeServer(self._server_name)
            self._owns_server = False

    def _notify_existing_instance(self) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self._server_name)
        if not socket.waitForConnected(CONNECT_TIMEOUT_MS):
            socket.abort()
            return False

        socket.write(b"activate")
        socket.flush()
        socket.waitForBytesWritten(CONNECT_TIMEOUT_MS)
        socket.disconnectFromServer()
        return True

    def _accept_pending_connections(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                continue
            socket.readyRead.connect(
                lambda current_socket=socket: self._handle_message(current_socket)
            )
            socket.disconnected.connect(socket.deleteLater)

            if socket.bytesAvailable() > 0:
                self._handle_message(socket)

    def _handle_message(self, socket: QLocalSocket) -> None:
        payload = bytes(socket.readAll()).strip().lower()
        if payload in {b"", b"activate"}:
            self.activation_requested.emit()


__all__ = [
    "DEFAULT_SERVER_NAME",
    "SingleInstanceCoordinator",
]
