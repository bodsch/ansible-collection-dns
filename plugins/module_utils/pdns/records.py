"""
records.py

PowerDNS RRset builder helpers.

This module converts higher-level record definitions (typically lists of dict-like items)
into RRset dictionaries compatible with the PowerDNS API payload format by calling
`build_rrset(...)`.

Imported utilities:
    - fqdn(zone, name): Build a fully-qualified domain name (usually ensuring trailing dot).
    - build_rrset(...): Create a PowerDNS RRset dict.
    - reverse_zone_names(module, network=...): Helper to compute reverse names for PTR records.

Design notes:
    - All public helpers return a list of RRset dictionaries (PowerDNS JSON-compatible).
    - Input records are typed as Mapping[str, Any] to support both dicts and similar structures.
    - `ptr_records()` historically relies on a `module` name in scope; for typing and robustness,
      an optional `module` argument is supported (preferred).
"""

from __future__ import annotations

import ipaddress
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Mapping, Optional, Sequence, Set

from ansible_collections.bodsch.dns.plugins.module_utils.pdns.utils import (
    build_rrset,
    fqdn,
)
from ansible_collections.bodsch.dns.plugins.module_utils.utils import reverse_zone_names

RRset = Dict[str, Any]
Record = Mapping[str, Any]


def host_records(
    zone: str,
    records: Sequence[Record],
    comment: Optional[str] = None,
    account: Optional[str] = None,
) -> List[RRset]:
    """
    Build A/AAAA/CNAME RRsets for host entries.

    Each input item can describe:
        - IPv4 address (`ip`) -> A record
        - IPv6 address (`ipv6`) -> AAAA record
        - alias list (`aliases`) -> CNAME records pointing to the canonical host name

    Args:
        zone: Forward DNS zone (e.g. "example.com" or "example.com.").
        records: Host definitions. Each record may contain keys:
            - name: host label (required)
            - ip: IPv4 address (optional)
            - ipv6: IPv6 address (optional)
            - aliases: list of alias labels (optional)
            - ttl: TTL seconds (optional, default 3600)
        comment: Optional comment stored on created RRsets.
        account: Optional account string (currently unused here; kept for API symmetry).

    Returns:
        list[RRset]: RRset dictionaries (PowerDNS API format). A host may produce:
            - 0..1 AAAA rrset
            - 0..1 A rrset
            - 0..N CNAME rrsets (one per alias)
    """
    _ = account  # explicitly unused

    rrsets: List[RRset] = []

    for record in records:
        name = fqdn(zone, str(record.get("name")))
        ttl = int(record.get("ttl", 3600))
        ipv4 = record.get("ip")
        ipv6 = record.get("ipv6")
        aliases = record.get("aliases")

        if ipv6:
            rrsets.append(
                build_rrset(
                    name=name,
                    rtype="AAAA",
                    ttl=ttl,
                    records=[str(ipv6)],
                    comment=comment or "",
                )
            )

        if ipv4:
            rrsets.append(
                build_rrset(
                    name=name,
                    rtype="A",
                    ttl=ttl,
                    records=[str(ipv4)],
                    comment=comment or "",
                )
            )

        if aliases:
            for a in aliases:
                rrsets.append(
                    build_rrset(
                        name=fqdn(zone, str(a)),
                        rtype="CNAME",
                        ttl=ttl,
                        records=[name],
                        comment=comment or "",
                    )
                )

    return rrsets


def srv_records(
    zone: str,
    records: Sequence[Record],
    comment: Optional[str] = None,
    account: Optional[str] = None,
) -> List[RRset]:
    """
    Build SRV RRsets grouped by SRV owner name.

    SRV record format (content):
        priority weight port target

    Input entries with the same `name` are aggregated into a single RRset.

    Args:
        zone: Forward DNS zone.
        records: SRV definitions. Each record should contain keys:
            - name: SRV owner name (e.g. "_sip._tcp")
            - weight: int
            - port: int
            - target: hostname label (will be fqdn()'d)
            - priority: int (optional, default 0)
            - ttl: int (optional, default 3600)
        comment: Optional comment stored on created RRsets.
        account: Optional account string (currently unused here; kept for API symmetry).

    Returns:
        list[RRset]: One RRset per unique SRV owner name.
    """
    _ = account  # explicitly unused

    rrsets: List[RRset] = []
    grouped: DefaultDict[str, List[Record]] = defaultdict(list)

    for service in records:
        grouped[str(service["name"])].append(service)

    for srv_name, entries in grouped.items():
        srv_content: List[Dict[str, Any]] = []
        ttl = 3600

        for entry in entries:
            ttl = int(entry.get("ttl", ttl))
            priority = int(entry.get("priority", 0))
            weight = int(entry["weight"])
            port = int(entry["port"])
            target = fqdn(zone, str(entry["target"]))

            srv_content.append(
                {"content": f"{priority} {weight} {port} {target}", "disabled": False}
            )

        rrsets.append(
            build_rrset(
                name=fqdn(zone, srv_name),
                rtype="SRV",
                ttl=ttl,
                records=srv_content,
                comment=comment or "",
            )
        )

    return rrsets


def mx_records(
    zone: str,
    records: Sequence[Record],
    comment: Optional[str] = None,
    account: Optional[str] = None,
) -> List[RRset]:
    """
    Build a single MX RRset for the zone apex.

    Each input record contributes one MX entry.

    Args:
        zone: Forward DNS zone.
        records: MX definitions. Each record may contain keys:
            - name: exchange host (string)
            - preference: int (optional, default 10)
            - ttl: int (optional, default 3600; last value wins)
        comment: Optional comment stored on the created RRset.
        account: Optional account string (currently unused here; kept for API symmetry).

    Returns:
        list[RRset]: A list containing exactly one MX RRset dict for the zone apex.

    Notes:
        TTL is overwritten per input record; the last record's TTL wins.
    """
    _ = account  # explicitly unused

    rrsets: List[RRset] = []
    mx_content: List[Dict[str, Any]] = []
    zone_fqdn = zone if zone.endswith(".") else f"{zone}."
    ttl = 3600

    for record in records:
        name = record.get("name")
        ttl = int(record.get("ttl", ttl))
        preference = int(record.get("preference", 10))

        mx_content.append(
            dict(content=fqdn(zone, f"{preference} {name}"), disabled=False)
        )

    rrsets.append(
        build_rrset(
            name=zone_fqdn,
            rtype="MX",
            ttl=ttl,
            records=mx_content,
            comment=comment or "",
        )
    )

    return rrsets


def txt_records(
    zone: str,
    records: Sequence[Record],
    comment: Optional[str] = None,
    account: Optional[str] = None,
) -> List[RRset]:
    """
    Build TXT RRsets from TXT entries.

    Each entry can specify either a single string (`text`) or a list of strings.
    Each string becomes a TXT record. PowerDNS expects TXT content wrapped in quotes.

    Args:
        zone: Forward DNS zone.
        records: TXT definitions. Each record may contain keys:
            - name: owner name label
            - text: str | list[str]
            - ttl: int (optional, default 3600)
        comment: Optional comment stored on created RRsets.
        account: Optional account string (currently unused here; kept for API symmetry).

    Returns:
        list[RRset]: One TXT RRset per input entry.
    """
    _ = account  # explicitly unused

    rrsets: List[RRset] = []

    for entry in records:
        name = fqdn(zone, str(entry.get("name")))
        ttl = int(entry.get("ttl", 3600))
        txt_data = entry.get("text")

        if txt_data is None:
            txt_items: List[str] = []
        elif isinstance(txt_data, str):
            txt_items = [txt_data]
        else:
            txt_items = [str(x) for x in txt_data]

        txt_content: List[Dict[str, Any]] = []
        for line in txt_items:
            txt_content.append({"content": f'"{line}"', "disabled": False})

        rrsets.append(
            build_rrset(
                name=name,
                rtype="TXT",
                ttl=ttl,
                records=txt_content,
                comment=comment or "",
            )
        )

    return rrsets


def ptr_records(
    zone: str,
    records: Sequence[Record],
    comment: Optional[str] = None,
    account: Optional[str] = None,
    module: Any = None,
) -> List[RRset]:
    """
    Build PTR RRsets for given host records.

    For each input record, one PTR RRset is created using the IPv4 address (`ip`)
    and the forward hostname as PTR target.

    Args:
        zone: Forward DNS zone (used to build PTR target FQDN).
        records: PTR definitions. Each record may contain keys:
            - name: host label
            - ip: IPv4 address string
            - ttl: int (optional, default 3600)
        comment: Optional comment stored on created RRsets.
        account: Optional account string (currently unused here; kept for API symmetry).
        module: Ansible module object passed to `reverse_zone_names(...)`.
            If omitted, this function attempts to use a global name `module`
            for backward compatibility.

    Returns:
        list[RRset]: List of PTR RRset dictionaries.

    Raises:
        NameError: If `module` is not provided and no global `module` exists.
    """
    _ = account  # explicitly unused

    if module is None:
        # Backward compatibility: attempt to use global `module` if present
        module = globals().get("module")
        if module is None:
            raise NameError(
                "ptr_records() requires `module` (Ansible module) to compute reverse names."
            )

    rrsets: List[RRset] = []

    for record in records:
        name = fqdn(zone, str(record.get("name")))
        ttl = int(record.get("ttl", 3600))
        ipv4 = record.get("ip")

        rev_name = reverse_zone_names(module, network=ipv4)

        rrsets.append(
            build_rrset(
                name=rev_name,
                rtype="PTR",
                ttl=ttl,
                records=[name],
                comment=comment or "",
            )
        )

    return rrsets


def build_ptr_rrsets_by_zone(
    *,
    forward_zone: str,
    hosts: Sequence[Record],
    prefix_v4: int = 24,
    prefix_v6: Optional[int] = 64,
    comment: Optional[str] = None,
    account: Optional[str] = None,
) -> Dict[str, List[RRset]]:
    """
    Build PTR RRsets grouped by reverse-zone.

    Output format:
        {
          "<reverse-zone>": [ <rrset>, <rrset>, ... ],
          ...
        }

    Reverse-zone computation:
        - IPv4 reverse zones are generated on octet boundaries: prefix_v4 must be 8, 16, or 24.
          Default is /24.
        - IPv6 reverse zones are generated on nibble boundaries: prefix_v6 must be a multiple of 4.
          Default is /64. If prefix_v6 is None, IPv6 processing is disabled.

    Args:
        forward_zone: Forward DNS zone (e.g. "example.com").
        hosts: Host definitions. Each host may contain keys:
            - name: host label (required)
            - ttl: int (optional, default 3600)
            - ip: IPv4 address string (optional)
            - ipv6: IPv6 address string (optional)
        prefix_v4: IPv4 reverse-zone prefix (8, 16, 24).
        prefix_v6: IPv6 reverse-zone prefix (multiple of 4, 1..128) or None to disable IPv6.
        comment: Optional comment stored on created RRsets.
        account: Optional account passed through to `build_rrset`.

    Returns:
        dict[str, list[RRset]]: Mapping reverse-zone -> list of PTR RRset dicts.

    Raises:
        ValueError: If `prefix_v4` is not one of {8,16,24} or `prefix_v6` is not a valid nibble boundary.
    """

    def _ipv4_reverse_zone(ip: ipaddress.IPv4Address, prefix: int) -> str:
        if prefix not in (8, 16, 24):
            raise ValueError(
                "prefix_v4 must be one of 8, 16, 24 (octet boundary reverse zones)."
            )
        host_octets = (32 - prefix) // 8
        labels = ip.reverse_pointer.split(".")
        return ".".join(labels[host_octets:])

    def _ipv6_reverse_zone(ip: ipaddress.IPv6Address, prefix: int) -> str:
        if prefix % 4 != 0 or not (0 < prefix <= 128):
            raise ValueError("prefix_v6 must be a multiple of 4 in range 1..128")
        host_nibbles = (128 - prefix) // 4
        labels = ip.reverse_pointer.split(".")
        return ".".join(labels[host_nibbles:])

    targets: DefaultDict[str, DefaultDict[str, Set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    ttls: DefaultDict[str, Dict[str, int]] = defaultdict(dict)

    for host in hosts or []:
        hostname = host.get("name")
        ttl = int(host.get("ttl", 3600))

        if not hostname:
            continue

        ptr_target = fqdn(forward_zone, str(hostname))

        ipv4 = host.get("ip")
        if ipv4:
            try:
                ip4 = ipaddress.IPv4Address(str(ipv4))
                rev_zone = _ipv4_reverse_zone(ip4, prefix_v4)
                ptr_name = f"{ip4.reverse_pointer}."
                targets[rev_zone][ptr_name].add(ptr_target)
                ttls[rev_zone].setdefault(ptr_name, ttl)
            except Exception:
                pass

        ipv6 = host.get("ipv6")
        if ipv6 and prefix_v6 is not None:
            try:
                ip6 = ipaddress.IPv6Address(str(ipv6))
                rev_zone = _ipv6_reverse_zone(ip6, int(prefix_v6))
                ptr_name = f"{ip6.reverse_pointer}."
                targets[rev_zone][ptr_name].add(ptr_target)
                ttls[rev_zone].setdefault(ptr_name, ttl)
            except Exception:
                pass

    rrsets_by_zone: Dict[str, List[RRset]] = {}

    for rev_zone, names in targets.items():
        zone_rrsets: List[RRset] = []

        for ptr_name, ptr_targets in sorted(names.items(), key=lambda x: x[0]):
            zone_rrsets.append(
                build_rrset(
                    name=ptr_name,
                    rtype="PTR",
                    ttl=ttls[rev_zone].get(ptr_name, 3600),
                    records=sorted(ptr_targets),
                    comment=comment or "",
                    account=account,
                )
            )

        rrsets_by_zone[rev_zone] = zone_rrsets

    return rrsets_by_zone
