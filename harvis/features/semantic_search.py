from __future__ import annotations

import math
import os
import re
import threading
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from defusedxml import ElementTree

from harvis.features.file_access import default_search_roots
from harvis.features.storage import harvis_data_dir, read_json, write_json

MAX_INDEXED_FILES = 30_000
MAX_CONTENT_CANDIDATES = 120
MAX_EXTRACTED_CHARACTERS = 80_000
MAX_RESULTS = 12
_SKIPPED_DIRECTORIES = {
    ".cache",
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "node_modules",
}
_TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".log",
    ".md",
    ".py",
    ".rtf",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
_CONTENT_SUFFIXES = _TEXT_SUFFIXES | {".docx", ".pdf"}
_STOP_WORDS = {
    "a",
    "about",
    "archivo",
    "archivos",
    "de",
    "del",
    "el",
    "en",
    "esa",
    "ese",
    "find",
    "i",
    "la",
    "last",
    "los",
    "me",
    "mi",
    "que",
    "semana",
    "sobre",
    "that",
    "the",
    "used",
    "use",
    "week",
    "yo",
}
_TOKEN_ALIASES = {
    "greece": {"greece", "grecia", "greek", "griego", "griega"},
    "grecia": {"greece", "grecia", "greek", "griego", "griega"},
    "invoice": {"invoice", "factura", "receipt", "recibo"},
    "factura": {"invoice", "factura", "receipt", "recibo"},
    "homework": {"homework", "tarea", "assignment"},
    "tarea": {"homework", "tarea", "assignment"},
}
_TYPE_HINTS = {
    "pdf": {".pdf"},
    "document": {".doc", ".docx", ".odt", ".pdf", ".rtf", ".txt"},
    "documento": {".doc", ".docx", ".odt", ".pdf", ".rtf", ".txt"},
    "photo": {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"},
    "foto": {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"},
    "image": {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"},
    "imagen": {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"},
    "video": {".avi", ".mkv", ".mov", ".mp4", ".webm"},
}


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value))
    without_marks = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^a-zA-Z0-9]+", " ", without_marks).casefold().split())


def _tokens(value: str) -> set[str]:
    found = {
        token
        for token in _normalize_text(value).split()
        if len(token) >= 2 and token not in _STOP_WORDS
    }
    expanded = set(found)
    for token in found:
        expanded.update(_TOKEN_ALIASES.get(token, ()))
    return expanded


class SemanticFileSearch:
    """Search local files using names, paths, recency, prior use, and bounded content."""

    def __init__(self, cache_path: Path | None = None) -> None:
        self.cache_path = cache_path or harvis_data_dir() / "semantic_file_index.json"
        self._lock = threading.RLock()

    def search(
        self,
        query: str,
        *,
        roots: list[Path] | None = None,
        limit: int = 8,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        clean_query = " ".join(str(query).split()).strip()[:500]
        query_tokens = _tokens(clean_query)
        if not query_tokens:
            raise ValueError("A descriptive file search query is required.")

        bounded_limit = max(1, min(MAX_RESULTS, int(limit)))
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        wants_recent = any(
            phrase in _normalize_text(clean_query)
            for phrase in ("last week", "recent", "semana pasada", "reciente")
        )
        type_suffixes = self._requested_suffixes(clean_query)

        with self._lock:
            cache = self._load_cache()
            candidates = self._scan_metadata(roots or default_search_roots(), cache)
            preliminary = []
            for path, record in candidates:
                if type_suffixes and path.suffix.casefold() not in type_suffixes:
                    continue
                metadata_tokens = set(record.get("metadata_tokens", []))
                overlap = len(query_tokens & metadata_tokens)
                recency = self._recency_score(record, current)
                preliminary.append((overlap * 4.0 + recency, path, record))

            preliminary.sort(key=lambda item: item[0], reverse=True)
            content_pool = preliminary[:MAX_CONTENT_CANDIDATES]
            for _, path, record in content_pool:
                if path.suffix.casefold() not in _CONTENT_SUFFIXES:
                    continue
                self._refresh_content_tokens(path, record)

            scored: list[tuple[float, Path, dict[str, Any], list[str]]] = []
            for _, path, record in preliminary:
                metadata_tokens = set(record.get("metadata_tokens", []))
                content_tokens = set(record.get("content_tokens", []))
                metadata_overlap = len(query_tokens & metadata_tokens)
                content_overlap = len(query_tokens & content_tokens)
                if metadata_overlap == 0 and content_overlap == 0:
                    continue
                recency = self._recency_score(record, current)
                score = metadata_overlap * 5.0 + content_overlap * 2.2 + recency
                reasons: list[str] = []
                if metadata_overlap:
                    reasons.append("name or folder match")
                if content_overlap:
                    reasons.append("document content match")
                if recency >= 1.0:
                    reasons.append("recently modified or opened")
                if wants_recent and recency < 0.2:
                    score *= 0.65
                scored.append((score, path, record, reasons))

            scored.sort(key=lambda item: (-item[0], item[1].name.casefold()))
            write_json(self.cache_path, cache)

        matches = [
            {
                "name": path.name,
                "path": str(path),
                "score": round(score, 3),
                "modified_at": str(record.get("modified_at", "")),
                "last_opened_at": str(record.get("last_opened_at", "")),
                "reason": ", ".join(reasons),
            }
            for score, path, record, reasons in scored[:bounded_limit]
        ]
        return {
            "status": "completed" if matches else "not_found",
            "query": clean_query,
            "count": len(matches),
            "matches": matches,
            "indexed_files": len(candidates),
        }

    def record_open(self, path: str | Path) -> None:
        resolved = Path(path).expanduser().resolve()
        with self._lock:
            cache = self._load_cache()
            key = str(resolved)
            record = cache.setdefault(key, {})
            record["last_opened_at"] = datetime.now(timezone.utc).isoformat()
            write_json(self.cache_path, cache)

    def clear(self) -> dict[str, Any]:
        with self._lock:
            write_json(self.cache_path, {})
        return {"status": "cleared", "path": str(self.cache_path)}

    @staticmethod
    def _requested_suffixes(query: str) -> set[str]:
        normalized = _normalize_text(query)
        requested: set[str] = set()
        for hint, suffixes in _TYPE_HINTS.items():
            if re.search(rf"\b{re.escape(hint)}\b", normalized):
                requested.update(suffixes)
        return requested

    def _scan_metadata(
        self,
        roots: list[Path],
        cache: dict[str, dict[str, Any]],
    ) -> list[tuple[Path, dict[str, Any]]]:
        found: list[tuple[Path, dict[str, Any]]] = []
        searched = 0
        for root in roots:
            root_path = Path(root).expanduser()
            if not root_path.exists():
                continue
            for current_root, directories, files in os.walk(root_path, topdown=True):
                directories[:] = [
                    directory
                    for directory in directories
                    if directory.casefold() not in _SKIPPED_DIRECTORIES
                ]
                for file_name in files:
                    searched += 1
                    if searched > MAX_INDEXED_FILES:
                        return found
                    path = (Path(current_root) / file_name).resolve()
                    try:
                        stat = path.stat()
                    except OSError:
                        continue
                    key = str(path)
                    record = cache.setdefault(key, {})
                    signature = [int(stat.st_size), int(stat.st_mtime_ns)]
                    if record.get("signature") != signature:
                        record.update(
                            {
                                "signature": signature,
                                "metadata_tokens": sorted(
                                    _tokens(f"{path.stem} {path.parent}")
                                ),
                                "content_tokens": [],
                                "modified_at": datetime.fromtimestamp(
                                    stat.st_mtime,
                                    timezone.utc,
                                ).isoformat(),
                                "accessed_at": datetime.fromtimestamp(
                                    stat.st_atime,
                                    timezone.utc,
                                ).isoformat(),
                            }
                        )
                    found.append((path, record))
        return found

    @staticmethod
    def _recency_score(record: dict[str, Any], now: datetime) -> float:
        timestamps = []
        for field in ("last_opened_at", "accessed_at", "modified_at"):
            value = str(record.get(field, ""))
            if not value:
                continue
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            timestamps.append(parsed.astimezone(timezone.utc))
        if not timestamps:
            return 0.0
        age_days = max(0.0, (now - max(timestamps)).total_seconds() / 86400.0)
        return 3.0 * math.exp(-age_days / 10.0)

    @staticmethod
    def _refresh_content_tokens(path: Path, record: dict[str, Any]) -> None:
        if record.get("content_tokens"):
            return
        text = _extract_document_text(path)
        if text:
            record["content_tokens"] = sorted(_tokens(text))[:5000]

    def _load_cache(self) -> dict[str, dict[str, Any]]:
        payload = read_json(self.cache_path, {})
        if not isinstance(payload, dict):
            return {}
        return {
            str(key): value
            for key, value in payload.items()
            if isinstance(value, dict)
        }


def _extract_document_text(path: Path) -> str:
    suffix = path.suffix.casefold()
    try:
        if suffix in _TEXT_SUFFIXES:
            return path.read_text(encoding="utf-8", errors="ignore")[
                :MAX_EXTRACTED_CHARACTERS
            ]
        if suffix == ".docx":
            with zipfile.ZipFile(path) as archive:
                data = archive.read("word/document.xml")
            root = ElementTree.fromstring(data)
            return " ".join(root.itertext())[:MAX_EXTRACTED_CHARACTERS]
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError:
                return ""
            reader = PdfReader(str(path))
            pieces: list[str] = []
            remaining = MAX_EXTRACTED_CHARACTERS
            for page in reader.pages[:12]:
                page_text = str(page.extract_text() or "")
                pieces.append(page_text[:remaining])
                remaining -= len(pieces[-1])
                if remaining <= 0:
                    break
            return " ".join(pieces)
    except Exception:
        return ""
    return ""


__all__ = ["SemanticFileSearch"]
