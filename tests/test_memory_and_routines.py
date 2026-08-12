
import pytest

from harvis.features.memory import MemoryStore
from harvis.features.routines import RoutineStore


def test_memory_store_round_trip_and_forget(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.json")

    assert store.remember("NovaLens folder", "D:/Projects/NovaLens")["status"] == "remembered"
    recalled = store.recall("novalens")

    assert recalled["count"] == 1
    assert recalled["memories"][0]["value"] == "D:/Projects/NovaLens"
    assert store.forget("NovaLens folder")["status"] == "forgotten"
    assert store.recall()["count"] == 0


@pytest.mark.parametrize(
    "key,value",
    [
        ("Gemini API key", "AQ.example"),
        ("login", "my password is example"),
        ("secret token", "example"),
    ],
)
def test_memory_store_rejects_secrets(tmp_path, key, value) -> None:
    store = MemoryStore(tmp_path / "memory.json")

    with pytest.raises(ValueError, match="does not store"):
        store.remember(key, value)


def test_routine_store_round_trip(tmp_path) -> None:
    store = RoutineStore(tmp_path / "routines.json")
    steps = [{"action": "open_url", "url": "https://example.com"}]

    assert store.save("Study mode", steps)["status"] == "saved"
    assert store.get("study MODE")["steps"] == steps
    assert store.list()["routines"][0]["name"] == "Study mode"
    assert store.delete("Study mode")["status"] == "deleted"
