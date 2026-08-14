from __future__ import annotations

from datetime import datetime, timezone

from harvis.features.offline_commands import OfflineCommandRouter
from harvis.features.proactive import ProactiveMonitor, ProactiveScheduleStore


def test_offline_router_executes_deterministic_commands() -> None:
    calls = []

    def execute(action, arguments):
        calls.append((action, arguments))
        return {"status": "completed"}

    router = OfflineCommandRouter()

    assert router.execute("Harvis volumen al 35%", execute)["offline"] is True
    assert calls[-1] == ("set_master_volume", {"percent": 35})

    assert router.execute("abre youtube", execute)["offline"] is True
    assert calls[-1][0] == "open_url"

    assert router.execute("explica computación cuántica", execute) is None


def test_proactive_schedule_runs_once_and_advances_daily(tmp_path) -> None:
    store = ProactiveScheduleStore(tmp_path / "schedule.json")
    store.schedule_reminder("One time", "2026-08-14T10:00:00+00:00")
    daily = store.schedule_reminder(
        "Daily",
        "2026-08-14T09:00:00+00:00",
        recurrence="daily",
    )

    due = store.take_due(now=datetime(2026, 8, 14, 11, tzinfo=timezone.utc))

    assert {item["value"] for item in due} == {"One time", "Daily"}
    remaining = store.list()["items"]
    assert len(remaining) == 1
    assert remaining[0]["id"] == daily["id"]
    assert remaining[0]["run_at"].startswith("2026-08-15T09:00:00")


def test_proactive_monitor_reports_completed_download(tmp_path) -> None:
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    temporary = downloads / "report.pdf.crdownload"
    temporary.write_bytes(b"partial")
    notifications = []
    monitor = ProactiveMonitor(
        ProactiveScheduleStore(tmp_path / "schedule.json"),
        on_notification=lambda *args: notifications.append(args),
        run_routine=lambda name: {"status": "completed"},
        downloads_directory=downloads,
    )

    monitor.poll_once()
    temporary.unlink()
    (downloads / "report.pdf").write_bytes(b"complete")
    monitor.poll_once()

    assert notifications[-1] == (
        "Download finished",
        "report.pdf",
        "success",
    )
