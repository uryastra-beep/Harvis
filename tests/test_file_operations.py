from pathlib import Path

from harvis.assistant import HarvisAssistant
from harvis.config import HarvisSettings
from harvis.features import file_operations


def test_move_item_records_a_safe_inverse(monkeypatch, tmp_path) -> None:
    source = tmp_path / "report.txt"
    destination = tmp_path / "Archive"
    source.write_text("report", encoding="utf-8")
    destination.mkdir()

    def resolve(name):
        return [source] if name == "report.txt" else [destination]

    monkeypatch.setattr(file_operations, "find_exact_paths", resolve)
    result = file_operations.move_item("report.txt", "Archive")

    assert result["status"] == "completed"
    assert (destination / "report.txt").exists()
    assert result["undo"]["action"] == "move_path_absolute"


def test_rename_never_overwrites(monkeypatch, tmp_path) -> None:
    source = tmp_path / "old.txt"
    target = tmp_path / "new.txt"
    source.write_text("old", encoding="utf-8")
    target.write_text("new", encoding="utf-8")
    monkeypatch.setattr(file_operations, "find_exact_paths", lambda name: [source])

    result = file_operations.rename_item("old.txt", "new.txt")

    assert result["status"] == "conflict"
    assert source.read_text(encoding="utf-8") == "old"
    assert target.read_text(encoding="utf-8") == "new"


def test_organize_folder_skips_conflicts(tmp_path) -> None:
    folder = tmp_path / "Downloads"
    folder.mkdir()
    (folder / "photo.png").write_bytes(b"image")
    (folder / "notes.txt").write_text("notes", encoding="utf-8")

    result = file_operations.organize_folder_by_type(folder)

    assert result["status"] == "completed"
    assert (folder / "Images" / "photo.png").exists()
    assert (folder / "Documents" / "notes.txt").exists()


def test_delete_requires_real_later_confirmation(monkeypatch, tmp_path) -> None:
    target = tmp_path / "delete-me.txt"
    target.write_text("data", encoding="utf-8")
    assistant = HarvisAssistant(HarvisSettings(assistant_mode="Silent"))
    deleted: list[Path] = []
    monkeypatch.setattr(
        "harvis.assistant.resolve_one_exact",
        lambda name: (target, None),
    )
    monkeypatch.setattr(
        "harvis.assistant.send_item_to_trash",
        lambda path: deleted.append(path) or {"status": "completed"},
    )

    first = assistant._execute_tool(
        "delete_exact_file_or_folder",
        {"name": "delete-me.txt"},
    )
    premature = assistant._execute_tool(
        "delete_exact_file_or_folder",
        {"name": "delete-me.txt"},
    )
    assistant._record_visual_confirmation_response("yes", complete_input=True)
    confirmed = assistant._execute_tool(
        "delete_exact_file_or_folder",
        {"name": "delete-me.txt"},
    )

    assert first["status"] == "confirmation_required"
    assert premature["status"] == "confirmation_required"
    assert confirmed["status"] == "completed"
    assert deleted == [target]
