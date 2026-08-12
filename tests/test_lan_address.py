from __future__ import annotations

from harvis import lan_address


def test_best_lan_ipv4_prefers_physical_adapter(monkeypatch) -> None:
    monkeypatch.setattr(
        lan_address,
        "_windows_physical_ipv4s",
        lambda: ["192.168.50.24"],
    )
    monkeypatch.setattr(lan_address, "_route_ipv4", lambda: "10.8.0.2")
    monkeypatch.setattr(
        lan_address,
        "_hostname_ipv4s",
        lambda: ["172.20.0.1"],
    )

    assert lan_address.best_lan_ipv4() == "192.168.50.24"


def test_candidates_filter_non_lan_and_duplicates(monkeypatch) -> None:
    monkeypatch.setattr(
        lan_address,
        "_windows_physical_ipv4s",
        lambda: ["192.168.1.20", "192.168.1.20"],
    )
    monkeypatch.setattr(lan_address, "_route_ipv4", lambda: None)
    monkeypatch.setattr(
        lan_address,
        "_hostname_ipv4s",
        lambda: ["127.0.0.1", "8.8.8.8", "10.0.0.5"],
    )

    assert lan_address.lan_ipv4_candidates() == ["192.168.1.20", "10.0.0.5"]


def test_best_lan_ipv4_falls_back_to_loopback(monkeypatch) -> None:
    monkeypatch.setattr(lan_address, "_windows_physical_ipv4s", lambda: [])
    monkeypatch.setattr(lan_address, "_route_ipv4", lambda: None)
    monkeypatch.setattr(lan_address, "_hostname_ipv4s", lambda: [])

    assert lan_address.best_lan_ipv4() == "127.0.0.1"
