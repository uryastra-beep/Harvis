from pathlib import Path

from harvis.features import file_access, named_links


def test_named_links_parser_and_exact_open(monkeypatch, tmp_path) -> None:
    path = tmp_path / "links.txt"
    path.write_text(
        "Oxford: https://englishhub.oup.com/\nWoot it: https://www.wootit.com/ghm/v4/home/\n",
        encoding="utf-8",
    )
    opened: list[str] = []
    monkeypatch.setattr(named_links, "open_default_browser", opened.append)

    result = named_links.open_named_link("OXFORD", path=path)

    assert result["status"] == "completed"
    assert opened == ["https://englishhub.oup.com/"]
    assert named_links.open_named_link("missing", path=path)["status"] == "not_found"


def test_find_exact_file_supports_stem_and_rejects_guessing(tmp_path) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()
    (first / "photo.png").write_bytes(b"one")
    (second / "photo.jpg").write_bytes(b"two")

    matches = file_access.find_exact_paths("photo", roots=[tmp_path])

    assert {path.name for path in matches} == {"photo.png", "photo.jpg"}


def test_open_exact_path_returns_ambiguity_without_opening(monkeypatch, tmp_path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "report.pdf").write_bytes(b"a")
    (tmp_path / "b" / "report.pdf").write_bytes(b"b")
    opened: list[Path] = []
    monkeypatch.setattr(file_access, "_open_with_default_application", opened.append)

    result = file_access.open_exact_path("report.pdf", roots=[tmp_path])

    assert result["status"] == "ambiguous"
    assert opened == []
