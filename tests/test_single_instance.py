from __future__ import annotations

from harvis.single_instance import SingleInstanceCoordinator


class _FakeSocket:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def readAll(self) -> bytes:
        payload = self._payload
        self._payload = b""
        return payload


def test_activate_message_requests_existing_window() -> None:
    coordinator = SingleInstanceCoordinator(server_name="HarvisTestActivation")
    activations: list[str] = []
    coordinator.activation_requested.connect(lambda: activations.append("activate"))

    coordinator._handle_message(_FakeSocket(b"ACTIVATE"))

    assert activations == ["activate"]


def test_unknown_message_does_not_request_activation() -> None:
    coordinator = SingleInstanceCoordinator(server_name="HarvisTestUnknown")
    activations: list[str] = []
    coordinator.activation_requested.connect(lambda: activations.append("activate"))

    coordinator._handle_message(_FakeSocket(b"unknown"))

    assert activations == []
