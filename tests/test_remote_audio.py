from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request

import pytest

from harvis.config import HarvisSettings
from harvis.remote_assistant import RemoteCapableHarvisAssistant
from harvis.remote_control import RemoteControlServer


class _FakeOutputStream:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.writes.append(bytes(data))


class _RemoteAudioFixture:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.audio_output = "pc"
        self.audio = b"\x01\x00\x02\x00\x03\x00"

    def command(self, text: str) -> None:
        self.commands.append(text)

    def status(self) -> dict:
        return {
            "status": "Listening",
            "response": "Ready",
            "mode": "Speaking",
            "microphone_muted": False,
            "assistant_running": True,
            "audio_output": self.audio_output,
        }

    def toggle_microphone(self) -> bool:
        return False

    def take_remote_audio(self) -> bytes:
        payload = self.audio
        self.audio = b""
        return payload

    def set_remote_audio_output(self, target: str) -> str:
        self.audio_output = target
        return target


def _json_request(
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


def _binary_request(url: str, path: str, *, token: str) -> tuple[int, bytes]:
    request = urllib.request.Request(
        f"{url}{path}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=3.0) as response:
        return response.status, response.read()


def test_phone_only_routes_voice_audio_away_from_pc_output() -> None:
    assistant = RemoteCapableHarvisAssistant(HarvisSettings(voice_volume=100))
    output = _FakeOutputStream()
    payload = b"\x10\x00\x20\x00\x30\x00\x40\x00"

    assert assistant.set_remote_audio_output("phone") == "phone"
    asyncio.run(assistant._voice._play_audio(output, payload))

    assert output.writes == []
    assert assistant.take_remote_audio() == payload
    assert assistant.remote_status()["audio_output"] == "phone"


def test_both_routes_voice_audio_to_pc_and_phone() -> None:
    assistant = RemoteCapableHarvisAssistant(HarvisSettings(voice_volume=100))
    output = _FakeOutputStream()
    payload = b"\x10\x00\x20\x00\x30\x00\x40\x00"

    assert assistant.set_remote_audio_output("both") == "both"
    asyncio.run(assistant._voice._play_audio(output, payload))

    assert output.writes == [payload]
    assert assistant.take_remote_audio() == payload


def test_remote_audio_output_rejects_unknown_target() -> None:
    assistant = RemoteCapableHarvisAssistant(HarvisSettings())

    with pytest.raises(ValueError):
        assistant.set_remote_audio_output("television")


def test_paired_remote_can_select_phone_audio_and_fetch_pcm() -> None:
    fixture = _RemoteAudioFixture()
    server = RemoteControlServer(
        command_handler=fixture.command,
        status_provider=fixture.status,
        microphone_toggle_handler=fixture.toggle_microphone,
        port=0,
    )
    server.start()
    try:
        url = f"http://127.0.0.1:{server.port}"
        pair_status, pair_body = _json_request(
            url,
            "/api/pair",
            method="POST",
            payload={"code": server.pairing_code},
        )
        token = pair_body["token"]
        output_status, output_body = _json_request(
            url,
            "/api/audio/output",
            method="POST",
            payload={"target": "phone"},
            token=token,
        )
        audio_status, audio_body = _binary_request(url, "/api/audio", token=token)

        assert pair_status == 200
        assert output_status == 200
        assert output_body["audio_output"] == "phone"
        assert fixture.audio_output == "phone"
        assert audio_status == 200
        assert audio_body == b"\x01\x00\x02\x00\x03\x00"
    finally:
        server.stop()

    assert fixture.audio_output == "pc"
