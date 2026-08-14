from __future__ import annotations

import json
import os
import platform
import re
import shutil
import sys
import tempfile
import threading
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harvis.credentials import CredentialStoreError, get_gemini_api_key
from harvis.features.storage import atomic_write_text, harvis_data_dir, read_json

MAX_LOG_TAIL_CHARACTERS = 120_000
_SECRET_PATTERN = re.compile(
    r"(?i)(api[_ -]?key|password|secret|token)(\s*[:=]\s*)([^\s,;]+)"
)
_GEMINI_KEY_PATTERN = re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")


def _redact_text(value: str) -> str:
    redacted = _SECRET_PATTERN.sub(r"\1\2<redacted>", str(value))
    return _GEMINI_KEY_PATTERN.sub("<redacted Gemini key>", redacted)


class RuntimeHealthSession:
    """Track clean shutdown and persist bounded crash reports without secrets."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or harvis_data_dir()
        self.marker_path = self.directory / "runtime.active"
        self.crash_path = self.directory / "last_crash.json"
        self.previous_unclean_shutdown = False
        self._previous_hook = None
        self._lock = threading.RLock()

    def start(self) -> bool:
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            self.previous_unclean_shutdown = self.marker_path.exists()
            atomic_write_text(
                self.marker_path,
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "started_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                + "\n",
            )
            if self._previous_hook is None:
                self._previous_hook = sys.excepthook
                sys.excepthook = self._handle_exception
        return self.previous_unclean_shutdown

    def stop(self) -> None:
        with self._lock:
            try:
                self.marker_path.unlink(missing_ok=True)
            except OSError:
                pass
            if self._previous_hook is not None:
                sys.excepthook = self._previous_hook
                self._previous_hook = None

    def _handle_exception(self, exception_type, exception, traceback_object) -> None:
        payload = {
            "at": datetime.now(timezone.utc).isoformat(),
            "type": getattr(exception_type, "__name__", "Exception"),
            "message": _redact_text(str(exception))[:2000],
            "traceback": _redact_text(
                "".join(
                    traceback.format_exception(
                        exception_type,
                        exception,
                        traceback_object,
                        limit=40,
                    )
                )
            )[-40_000:],
        }
        try:
            atomic_write_text(
                self.crash_path,
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            )
        except OSError:
            pass
        previous = self._previous_hook
        if previous is not None:
            previous(exception_type, exception, traceback_object)


class RuntimeDiagnostics:
    """Run local self-checks and export a privacy-bounded support bundle."""

    def __init__(
        self,
        directory: Path | None = None,
        *,
        settings_path: Path | None = None,
    ) -> None:
        self.directory = directory or harvis_data_dir()
        self.settings_path = settings_path or self.directory / "settings.json"

    def run_self_check(self) -> dict[str, Any]:
        checks = [
            self._check_data_directory(),
            self._check_free_space(),
            self._check_credentials(),
            self._check_settings(),
            self._check_last_crash(),
        ]
        failures = [check for check in checks if check["status"] == "failed"]
        warnings = [check for check in checks if check["status"] == "warning"]
        return {
            "status": "failed" if failures else "warning" if warnings else "healthy",
            "checks": checks,
            "failures": len(failures),
            "warnings": len(warnings),
            "platform": platform.platform(),
            "python": platform.python_version(),
        }

    def export_bundle(self, destination: Path | None = None) -> dict[str, Any]:
        self.directory.mkdir(parents=True, exist_ok=True)
        target_directory = destination or self.directory / "diagnostics"
        target_directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        archive_path = target_directory / f"Harvis-Diagnostics-{stamp}.zip"
        report = self.run_self_check()
        with zipfile.ZipFile(
            archive_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            archive.writestr(
                "self-check.json",
                json.dumps(report, indent=2, ensure_ascii=False),
            )
            settings = read_json(self.settings_path, {})
            if isinstance(settings, dict):
                safe_settings = {
                    key: "<redacted>"
                    if any(
                        marker in key.casefold()
                        for marker in ("key", "password", "secret", "token", "name")
                    )
                    else value
                    for key, value in settings.items()
                }
                archive.writestr(
                    "settings-redacted.json",
                    json.dumps(safe_settings, indent=2, ensure_ascii=False),
                )
            for source_name, archive_name in (
                ("harvis.log", "harvis-log-tail.txt"),
                ("activity.jsonl", "activity-tail.jsonl"),
                ("last_crash.json", "last-crash.json"),
            ):
                source = self.directory / source_name
                try:
                    text = source.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                archive.writestr(
                    archive_name,
                    _redact_text(text[-MAX_LOG_TAIL_CHARACTERS:]),
                )
        return {
            "status": "completed",
            "path": str(archive_path),
            "self_check": report["status"],
        }

    def _check_data_directory(self) -> dict[str, str]:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".harvis-self-check-",
                dir=self.directory,
            )
            os.close(descriptor)
            Path(temporary_name).unlink(missing_ok=True)
        except OSError as exc:
            return {
                "name": "data_directory",
                "status": "failed",
                "message": _redact_text(str(exc))[:500],
            }
        return {
            "name": "data_directory",
            "status": "healthy",
            "message": "Harvis can read and write its local data directory.",
        }

    def _check_free_space(self) -> dict[str, str]:
        try:
            free_bytes = shutil.disk_usage(self.directory.parent).free
        except OSError as exc:
            return {
                "name": "free_space",
                "status": "warning",
                "message": _redact_text(str(exc))[:500],
            }
        free_mb = free_bytes // (1024 * 1024)
        status = "healthy" if free_mb >= 500 else "warning"
        return {
            "name": "free_space",
            "status": status,
            "message": f"{free_mb} MB available.",
        }

    @staticmethod
    def _check_credentials() -> dict[str, str]:
        try:
            configured = bool(get_gemini_api_key())
        except CredentialStoreError as exc:
            return {
                "name": "gemini_credentials",
                "status": "failed",
                "message": _redact_text(str(exc))[:500],
            }
        return {
            "name": "gemini_credentials",
            "status": "healthy" if configured else "warning",
            "message": "Gemini API key is configured."
            if configured
            else "Gemini API key is not configured; offline commands remain available.",
        }

    def _check_settings(self) -> dict[str, str]:
        if not self.settings_path.exists():
            return {
                "name": "settings",
                "status": "warning",
                "message": "Settings have not been saved yet.",
            }
        payload = read_json(self.settings_path, None)
        return {
            "name": "settings",
            "status": "healthy" if isinstance(payload, dict) else "failed",
            "message": "Settings file is valid JSON."
            if isinstance(payload, dict)
            else "Settings file is not valid JSON.",
        }

    def _check_last_crash(self) -> dict[str, str]:
        crash_path = self.directory / "last_crash.json"
        if not crash_path.exists():
            return {
                "name": "last_crash",
                "status": "healthy",
                "message": "No saved crash report.",
            }
        return {
            "name": "last_crash",
            "status": "warning",
            "message": f"A crash report exists at {crash_path}.",
        }


__all__ = ["RuntimeDiagnostics", "RuntimeHealthSession"]
