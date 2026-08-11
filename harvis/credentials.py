from __future__ import annotations

import contextlib
import ctypes
import os
import platform
import tempfile
from ctypes import wintypes
from pathlib import Path

GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
WINDOWS_CREDENTIAL_TARGET = "Harvis/GeminiApiKey"
WINDOWS_CREDENTIAL_USERNAME = "Harvis"


class CredentialStoreError(RuntimeError):
    """Raised when Harvis cannot read or write a stored credential."""


def get_gemini_api_key() -> str:
    """Return the saved Gemini API key, falling back to the process environment."""

    stored = ""
    if platform.system() == "Windows":
        stored = _read_windows_credential()
    else:
        stored = _read_file_credential(_default_secret_path())

    if stored.strip():
        return stored.strip()
    return os.getenv(GEMINI_API_KEY_ENV, "").strip()


def save_gemini_api_key(api_key: str) -> None:
    """Persist a Gemini API key without placing it in Harvis settings.json."""

    value = str(api_key).strip()
    if not value:
        raise ValueError("A Gemini API key is required.")

    if platform.system() == "Windows":
        _write_windows_credential(value)
    else:
        _write_file_credential(_default_secret_path(), value)


def sync_gemini_api_key_environment() -> bool:
    """Return whether a Gemini API key is available without exporting it."""

    try:
        value = get_gemini_api_key()
    except CredentialStoreError:
        value = os.getenv(GEMINI_API_KEY_ENV, "").strip()

    return bool(value)


def _default_secret_path() -> Path:
    config_home = os.getenv("XDG_CONFIG_HOME", "").strip()
    base = Path(config_home) if config_home else Path.home() / ".config"
    return base / "Harvis" / "gemini_api_key"


def _read_file_credential(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""
    except OSError as exc:
        raise CredentialStoreError("Harvis could not read the saved Gemini API key.") from exc


def _write_file_credential(path: Path, api_key: str) -> None:
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            path.parent.chmod(0o700)

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            text=True,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(api_key)
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.chmod(0o600)
        os.replace(temporary_path, path)
        temporary_path = None
        with contextlib.suppress(OSError):
            path.chmod(0o600)
    except OSError as exc:
        raise CredentialStoreError("Harvis could not save the Gemini API key.") from exc
    finally:
        if temporary_path is not None:
            with contextlib.suppress(OSError):
                temporary_path.unlink(missing_ok=True)


class _CredentialW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def _windows_api():
    advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    advapi32.CredWriteW.argtypes = [ctypes.POINTER(_CredentialW), wintypes.DWORD]
    advapi32.CredWriteW.restype = wintypes.BOOL
    advapi32.CredReadW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(_CredentialW)),
    ]
    advapi32.CredReadW.restype = wintypes.BOOL
    advapi32.CredFree.argtypes = [ctypes.c_void_p]
    advapi32.CredFree.restype = None
    return advapi32


def _read_windows_credential() -> str:
    advapi32 = _windows_api()
    credential_pointer = ctypes.POINTER(_CredentialW)()

    if not advapi32.CredReadW(
        WINDOWS_CREDENTIAL_TARGET,
        1,
        0,
        ctypes.byref(credential_pointer),
    ):
        error_code = ctypes.get_last_error()
        if error_code == 1168:
            return ""
        raise CredentialStoreError(
            f"Windows Credential Manager could not read the Gemini API key (error {error_code})."
        )

    try:
        credential = credential_pointer.contents
        if not credential.CredentialBlob or credential.CredentialBlobSize <= 0:
            return ""
        raw_value = ctypes.string_at(
            credential.CredentialBlob,
            credential.CredentialBlobSize,
        )
        return raw_value.decode("utf-16-le").rstrip("\x00")
    except (UnicodeDecodeError, ValueError) as exc:
        raise CredentialStoreError(
            "The saved Gemini API key could not be decoded."
        ) from exc
    finally:
        advapi32.CredFree(credential_pointer)


def _write_windows_credential(api_key: str) -> None:
    advapi32 = _windows_api()
    blob = api_key.encode("utf-16-le")
    blob_buffer = ctypes.create_string_buffer(blob)

    credential = _CredentialW()
    credential.Flags = 0
    credential.Type = 1
    credential.TargetName = WINDOWS_CREDENTIAL_TARGET
    credential.Comment = "Gemini API key saved by Harvis"
    credential.CredentialBlobSize = len(blob)
    credential.CredentialBlob = ctypes.cast(
        blob_buffer,
        ctypes.POINTER(ctypes.c_ubyte),
    )
    credential.Persist = 2
    credential.AttributeCount = 0
    credential.Attributes = None
    credential.TargetAlias = None
    credential.UserName = WINDOWS_CREDENTIAL_USERNAME

    if not advapi32.CredWriteW(ctypes.byref(credential), 0):
        error_code = ctypes.get_last_error()
        raise CredentialStoreError(
            f"Windows Credential Manager could not save the Gemini API key (error {error_code})."
        )
