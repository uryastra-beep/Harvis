from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from harvis.remote_control import MAX_REMOTE_COMMAND_CHARACTERS, RemoteControlServer


def _request(
    url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    token: str | None = None,
) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{url}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=3.0) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _server() -> tuple[RemoteControlServer, list[str]]:
    commands: list[str] = []
    server = RemoteControlServer(
        command_handler=commands.append,
        status_provider=lambda: {
            "status": "Listening",
            "response": "Ready",
            "mode": "Speaking",
            "microphone_muted": False,
            "assistant_running": True,
        },
        microphone_toggle_handler=lambda: True,
        port=0,
    )
    server.start()
    return server, commands


def test_remote_requires_pairing_for_status_and_commands() -> None:
    server, commands = _server()
    try:
        url = f"http://127.0.0.1:{server.port}"
        status_code, status_body = _request(url, "/api/status")
        command_code, command_body = _request(
            url,
            "/api/command",
            method="POST",
            payload={"command": "Open Spotify"},
        )

        assert status_code == 401
        assert status_body["error"] == "Pairing is required."
        assert command_code == 401
        assert command_body["error"] == "Pairing is required."
        assert commands == []
    finally:
        server.stop()


def test_correct_pairing_code_authorizes_mobile_command() -> None:
    server, commands = _server()
    try:
        url = f"http://127.0.0.1:{server.port}"
        pair_code, pair_body = _request(
            url,
            "/api/pair",
            method="POST",
            payload={"code": server.pairing_code},
        )
        token = pair_body["token"]
        status_code, status_body = _request(url, "/api/status", token=token)
        command_code, command_body = _request(
            url,
            "/api/command",
            method="POST",
            payload={"command": "  Open   Spotify  "},
            token=token,
        )

        assert pair_code == 200
        assert status_code == 200
        assert status_body["status"] == "Listening"
        assert command_code == 202
        assert command_body["status"] == "queued"
        assert commands == ["Open Spotify"]
    finally:
        server.stop()


def test_incorrect_pairing_code_is_rejected() -> None:
    server, _ = _server()
    try:
        url = f"http://127.0.0.1:{server.port}"
        wrong_code = "000000" if server.pairing_code != "000000" else "999999"
        status_code, body = _request(
            url,
            "/api/pair",
            method="POST",
            payload={"code": wrong_code},
        )

        assert status_code == 401
        assert body["error"] == "Incorrect pairing code."
    finally:
        server.stop()


def test_remote_microphone_toggle_uses_authenticated_callback() -> None:
    toggle_calls = 0

    def toggle() -> bool:
        nonlocal toggle_calls
        toggle_calls += 1
        return True

    server = RemoteControlServer(
        command_handler=lambda command: None,
        status_provider=dict,
        microphone_toggle_handler=toggle,
        port=0,
    )
    server.start()
    try:
        url = f"http://127.0.0.1:{server.port}"
        _, pair_body = _request(
            url,
            "/api/pair",
            method="POST",
            payload={"code": server.pairing_code},
        )
        status_code, body = _request(
            url,
            "/api/microphone/toggle",
            method="POST",
            payload={},
            token=pair_body["token"],
        )

        assert status_code == 200
        assert body["microphone_muted"] is True
        assert toggle_calls == 1
    finally:
        server.stop()


def test_remote_rejects_invalid_port() -> None:
    with pytest.raises(ValueError):
        RemoteControlServer(
            command_handler=lambda command: None,
            status_provider=dict,
            microphone_toggle_handler=lambda: False,
            port=70000,
        )


def test_remote_rejects_oversized_authenticated_command() -> None:
    server, commands = _server()
    try:
        url = f"http://127.0.0.1:{server.port}"
        _, pair_body = _request(
            url,
            "/api/pair",
            method="POST",
            payload={"code": server.pairing_code},
        )
        status_code, body = _request(
            url,
            "/api/command",
            method="POST",
            payload={"command": "x" * (MAX_REMOTE_COMMAND_CHARACTERS + 1)},
            token=pair_body["token"],
        )

        assert status_code == 413
        assert body["error"] == "Command is too long."
        assert commands == []
    finally:
        server.stop()
