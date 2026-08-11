import os
import stat
from pathlib import Path

from harvis import credentials
from harvis.credentials import (
    GEMINI_API_KEY_ENV,
    _read_file_credential,
    _write_file_credential,
)


def test_file_credential_round_trip(tmp_path: Path) -> None:
    secret_path = tmp_path / "Harvis" / "gemini_api_key"

    _write_file_credential(secret_path, "test-api-key")

    assert _read_file_credential(secret_path) == "test-api-key"

    if os.name != "nt":
        assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600


def test_missing_file_credential_returns_empty_string(tmp_path: Path) -> None:
    secret_path = tmp_path / "Harvis" / "missing_key"

    assert _read_file_credential(secret_path) == ""


def test_saved_key_is_not_exported_to_child_process_environment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    secret_path = tmp_path / "Harvis" / "gemini_api_key"
    monkeypatch.delenv(GEMINI_API_KEY_ENV, raising=False)
    monkeypatch.setattr(credentials.platform, "system", lambda: "Linux")
    monkeypatch.setattr(credentials, "_default_secret_path", lambda: secret_path)

    credentials.save_gemini_api_key("stored-only-key")

    assert credentials.get_gemini_api_key() == "stored-only-key"
    assert GEMINI_API_KEY_ENV not in os.environ
    assert credentials.sync_gemini_api_key_environment() is True
    assert GEMINI_API_KEY_ENV not in os.environ
