from __future__ import annotations

import ctypes
import platform
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from harvis.features.storage import harvis_data_dir, read_json, write_json

MAX_SCHEDULED_ITEMS = 100
SUPPORTED_RECURRENCES = {"once", "daily", "weekly"}
NotificationCallback = Callable[[str, str, str], None]
RoutineCallback = Callable[[str], dict[str, Any]]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str) -> datetime:
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError("A scheduled date and time is required.")
    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError("Scheduled time must be a valid ISO-8601 date and time.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.astimezone(timezone.utc)


class ProactiveScheduleStore:
    """Persist bounded reminders and guarded routine schedules."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or harvis_data_dir() / "proactive_schedule.json"
        self._lock = threading.RLock()

    def schedule_reminder(
        self,
        message: str,
        run_at: str,
        *,
        recurrence: str = "once",
    ) -> dict[str, Any]:
        clean_message = " ".join(str(message).split()).strip()[:500]
        if not clean_message:
            raise ValueError("A reminder message is required.")
        return self._save_item(
            kind="reminder",
            value=clean_message,
            run_at=run_at,
            recurrence=recurrence,
        )

    def schedule_routine(
        self,
        routine_name: str,
        run_at: str,
        *,
        recurrence: str = "once",
    ) -> dict[str, Any]:
        clean_name = " ".join(str(routine_name).split()).strip()[:80]
        if not clean_name:
            raise ValueError("A routine name is required.")
        return self._save_item(
            kind="routine",
            value=clean_name,
            run_at=run_at,
            recurrence=recurrence,
        )

    def list(self) -> dict[str, Any]:
        with self._lock:
            items = list(self._load().values())
        items.sort(key=lambda item: str(item.get("run_at", "")))
        return {
            "status": "completed",
            "count": len(items),
            "items": items,
        }

    def cancel(self, item_id: str) -> dict[str, Any]:
        normalized_id = str(item_id).strip()
        with self._lock:
            items = self._load()
            removed = items.pop(normalized_id, None)
            if removed is not None:
                write_json(self.path, items)
        return {
            "status": "cancelled" if removed is not None else "not_found",
            "id": normalized_id,
        }

    def take_due(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        current = (now or _utc_now()).astimezone(timezone.utc)
        due: list[dict[str, Any]] = []
        with self._lock:
            items = self._load()
            changed = False
            for item_id, item in list(items.items()):
                try:
                    scheduled_at = _parse_datetime(str(item.get("run_at", "")))
                except ValueError:
                    items.pop(item_id, None)
                    changed = True
                    continue
                if scheduled_at > current:
                    continue
                due.append(dict(item))
                recurrence = str(item.get("recurrence", "once"))
                if recurrence == "daily":
                    next_run = scheduled_at
                    while next_run <= current:
                        next_run += timedelta(days=1)
                    item["run_at"] = next_run.isoformat()
                elif recurrence == "weekly":
                    next_run = scheduled_at
                    while next_run <= current:
                        next_run += timedelta(days=7)
                    item["run_at"] = next_run.isoformat()
                else:
                    items.pop(item_id, None)
                changed = True
            if changed:
                write_json(self.path, items)
        return due

    def _save_item(
        self,
        *,
        kind: str,
        value: str,
        run_at: str,
        recurrence: str,
    ) -> dict[str, Any]:
        normalized_recurrence = str(recurrence).strip().casefold() or "once"
        if normalized_recurrence not in SUPPORTED_RECURRENCES:
            raise ValueError("Recurrence must be once, daily, or weekly.")
        scheduled_at = _parse_datetime(run_at)
        item_id = uuid.uuid4().hex[:12]
        item = {
            "id": item_id,
            "kind": kind,
            "value": value,
            "run_at": scheduled_at.isoformat(),
            "recurrence": normalized_recurrence,
            "created_at": _utc_now().isoformat(),
        }
        with self._lock:
            items = self._load()
            if len(items) >= MAX_SCHEDULED_ITEMS:
                raise ValueError(
                    f"Harvis supports at most {MAX_SCHEDULED_ITEMS} scheduled items."
                )
            items[item_id] = item
            write_json(self.path, items)
        return {"status": "scheduled", **item}

    def _load(self) -> dict[str, dict[str, Any]]:
        payload = read_json(self.path, {})
        if not isinstance(payload, dict):
            return {}
        return {
            str(key): value
            for key, value in payload.items()
            if isinstance(value, dict)
        }


class ProactiveMonitor:
    """Run lightweight local reminders, routine schedules, and system checks."""

    TEMPORARY_DOWNLOAD_SUFFIXES = (".crdownload", ".part", ".download")

    def __init__(
        self,
        schedule: ProactiveScheduleStore,
        *,
        on_notification: NotificationCallback,
        run_routine: RoutineCallback,
        downloads_directory: Path | None = None,
        battery_threshold: int = 20,
        monitor_downloads: bool = True,
        poll_seconds: float = 5.0,
    ) -> None:
        self.schedule = schedule
        self._on_notification = on_notification
        self._run_routine = run_routine
        self._downloads_directory = downloads_directory or Path.home() / "Downloads"
        self._battery_threshold = max(5, min(50, int(battery_threshold)))
        self._monitor_downloads = bool(monitor_downloads)
        self._poll_seconds = max(1.0, min(60.0, float(poll_seconds)))
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._download_baseline: set[str] | None = None
        self._battery_alerted = False

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def configure(
        self,
        *,
        battery_threshold: int,
        monitor_downloads: bool,
    ) -> None:
        self._battery_threshold = max(5, min(50, int(battery_threshold)))
        self._monitor_downloads = bool(monitor_downloads)

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="harvis-proactive-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def poll_once(self, *, now: datetime | None = None) -> None:
        for item in self.schedule.take_due(now=now):
            kind = str(item.get("kind", ""))
            value = str(item.get("value", ""))
            if kind == "routine":
                try:
                    result = self._run_routine(value)
                except Exception as exc:
                    self._notify("Routine failed", f"{value}: {exc}", "error")
                    continue
                status = str(result.get("status", "completed"))
                severity = "success" if status == "completed" else "warning"
                self._notify(
                    "Scheduled routine",
                    f"{value}: {status.replace('_', ' ')}",
                    severity,
                )
            elif kind == "reminder":
                self._notify("Harvis reminder", value, "info")

        self._check_downloads()
        self._check_battery()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.poll_once()
            except Exception:
                # Proactive checks are best effort and must never stop Harvis.
                pass
            self._stop_event.wait(self._poll_seconds)

    def _check_downloads(self) -> None:
        if not self._monitor_downloads or not self._downloads_directory.exists():
            self._download_baseline = None
            return
        try:
            current = {
                path.name
                for path in self._downloads_directory.iterdir()
                if path.is_file()
            }
        except OSError:
            return
        previous = self._download_baseline
        self._download_baseline = current
        if previous is None:
            return
        for temporary_name in previous - current:
            suffix = next(
                (
                    candidate
                    for candidate in self.TEMPORARY_DOWNLOAD_SUFFIXES
                    if temporary_name.casefold().endswith(candidate)
                ),
                None,
            )
            if suffix is None:
                continue
            final_name = temporary_name[: -len(suffix)]
            if final_name in current:
                self._notify(
                    "Download finished",
                    final_name,
                    "success",
                )

    def _check_battery(self) -> None:
        status = _battery_status()
        if status is None:
            return
        percent, plugged_in = status
        if plugged_in or percent > self._battery_threshold + 5:
            self._battery_alerted = False
            return
        if percent <= self._battery_threshold and not self._battery_alerted:
            self._battery_alerted = True
            self._notify(
                "Battery is low",
                f"Battery is at {percent}%. Connect the charger when convenient.",
                "warning",
            )

    def _notify(self, title: str, message: str, severity: str) -> None:
        self._on_notification(str(title), str(message), str(severity))


def _battery_status() -> tuple[int, bool] | None:
    system_name = platform.system()
    if system_name == "Windows":
        class _SystemPowerStatus(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_ubyte),
                ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte),
                ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", ctypes.c_ulong),
                ("BatteryFullLifeTime", ctypes.c_ulong),
            ]

        status = _SystemPowerStatus()
        try:
            if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
                return None
        except (AttributeError, OSError):
            return None
        if status.BatteryLifePercent == 255:
            return None
        return int(status.BatteryLifePercent), status.ACLineStatus == 1

    if system_name == "Linux":
        for battery in Path("/sys/class/power_supply").glob("BAT*"):
            try:
                percent = int((battery / "capacity").read_text().strip())
                state = (battery / "status").read_text().strip().casefold()
            except (OSError, ValueError):
                continue
            return percent, state in {"charging", "full", "not charging"}
    return None


__all__ = [
    "MAX_SCHEDULED_ITEMS",
    "SUPPORTED_RECURRENCES",
    "ProactiveMonitor",
    "ProactiveScheduleStore",
]
