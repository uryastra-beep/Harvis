from __future__ import annotations

import ipaddress
import platform
import socket
import subprocess


_RFC1918_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)

_WINDOWS_PHYSICAL_IP_COMMAND = r"""
$ErrorActionPreference = 'SilentlyContinue'
$physical = Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' }
$rows = foreach ($adapter in $physical) {
    $iface = Get-NetIPInterface -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
    $addresses = Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.AddressState -eq 'Preferred' -and $_.IPAddress -notlike '169.254.*' }
    foreach ($address in $addresses) {
        [PSCustomObject]@{
            IP = $address.IPAddress
            Metric = $(if ($iface) { $iface.InterfaceMetric } else { 9999 })
        }
    }
}
$rows | Sort-Object Metric | Select-Object -ExpandProperty IP
""".strip()


def _is_lan_ipv4(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return False
    return isinstance(address, ipaddress.IPv4Address) and any(
        address in network for network in _RFC1918_NETWORKS
    )


def _unique_lan_ipv4s(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = str(value).strip()
        if not _is_lan_ipv4(candidate) or candidate in seen:
            continue
        seen.add(candidate)
        result.append(candidate)
    return result


def _windows_physical_ipv4s() -> list[str]:
    """Return active physical-adapter IPv4 addresses, best metric first."""

    if platform.system() != "Windows":
        return []

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                _WINDOWS_PHYSICAL_IP_COMMAND,
            ],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
            creationflags=creation_flags,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    if completed.returncode != 0:
        return []
    return _unique_lan_ipv4s(completed.stdout.splitlines())


def _route_ipv4() -> str | None:
    """Return the IPv4 selected by the OS route table as a fallback."""

    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        address = str(probe.getsockname()[0])
        return address if _is_lan_ipv4(address) else None
    except OSError:
        return None
    finally:
        probe.close()


def _hostname_ipv4s() -> list[str]:
    try:
        _hostname, _aliases, addresses = socket.gethostbyname_ex(socket.gethostname())
    except OSError:
        return []
    return _unique_lan_ipv4s(list(addresses))


def lan_ipv4_candidates() -> list[str]:
    """Return usable LAN IPv4 addresses in preference order.

    On Windows, real physical adapters are preferred so VPN, WSL, Hyper-V,
    VMware, VirtualBox, Tailscale, and similar virtual routes do not become the
    phone URL merely because they own the current Internet route.
    """

    candidates: list[str] = []
    candidates.extend(_windows_physical_ipv4s())

    route_address = _route_ipv4()
    if route_address:
        candidates.append(route_address)

    candidates.extend(_hostname_ipv4s())
    return _unique_lan_ipv4s(candidates)


def best_lan_ipv4() -> str:
    candidates = lan_ipv4_candidates()
    return candidates[0] if candidates else "127.0.0.1"


__all__ = ["best_lan_ipv4", "lan_ipv4_candidates"]
