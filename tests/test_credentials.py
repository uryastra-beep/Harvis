from pathlib import Path

from harvis.credentials import _read_file_credential, _write_file_credential


def test_file_credential_round_trip(tmp_path: Path) -> None:
    secret_path = tmp_path / "Harvis" / "gemini_api_key"

    _write_file_credential(secret_path, "test-api-key")

    assert _read_file_credential(secret_path) == "test-api-key"


def test_missing_file_credential_returns_empty_string(tmp_path: Path) -> None:
    secret_path = tmp_path / "Harvis" / "missing_key"

    assert _read_file_credential(secret_path) == ""
