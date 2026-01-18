#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
utils.py

Utility helpers for building PowerDNS-compatible RRset payloads and DNS helper values.

This module provides:
    - `generate_serial()`: Generate an RFC-1912-style SOA serial number based on UTC date.
    - `fqdn()`: Normalize record names into fully-qualified domain names (FQDNs).
    - `build_rrset()`: Build a PowerDNS RRset dictionary suitable for API PATCH/POST payloads.

Intended usage:
    These helpers are consumed by other PowerDNS-related modules to construct API payloads
    and normalize hostnames.

Notes:
    - `generate_serial()` uses a `YYYYMMDDNN` format with a two-digit daily counter.
    - `fqdn()` ensures trailing dots and supports '@' as zone apex.
    - `build_rrset()` ensures the rrset `name` has a trailing dot and normalizes record
      entries into PowerDNS API `{content, disabled}` objects. An optional comment is
      added under `comments`.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, Mapping, Optional, Sequence, Union

RRsetRecordInput = Union[str, Mapping[str, Any]]
RRset = Dict[str, Any]


def generate_serial(base_serial: Optional[Union[int, str]] = None) -> int:
    """
    Generate a date-based SOA serial in the form `YYYYMMDDNN` (UTC).

    The serial is based on today's UTC date and a two-digit counter:
        - First call of the day: YYYYMMDD01
        - If `base_serial` starts with today's date (YYYYMMDD), the counter is increased by 1.

    Args:
        base_serial: Optional existing serial value (int or str). If provided and it matches
            today's date prefix (YYYYMMDD), its last two digits are interpreted as the counter
            and incremented.

    Returns:
        int: The generated serial number.

    Raises:
        ValueError: If `base_serial` matches today's prefix but its last two characters
            are not a valid integer counter.
    """
    today = datetime.datetime.utcnow().strftime("%Y%m%d")
    counter = 1
    serial = int(f"{today}{counter:02d}")

    # Optional: increment the counter if the existing serial is from today.
    if base_serial and str(base_serial).startswith(today):
        old_counter = int(str(base_serial)[-2:])
        counter = old_counter + 1
        serial = int(f"{today}{counter:02d}")

    return serial


def fqdn(zone: str, name: str) -> str:
    """
    Normalize a record name into a fully-qualified domain name (FQDN).

    Rules:
        - '@' maps to the zone apex (`<zone>.`)
        - If `name` already ends with '.', it is returned unchanged.
        - If `name` already ends with `zone`, a trailing dot is added.
        - Otherwise, `name` is treated as a label relative to `zone` and `.<zone>.` is appended.

    Examples:
        - fqdn("acme-inc.com", "srv001")              -> "srv001.acme-inc.com."
        - fqdn("acme-inc.com", "srv001.acme-inc.com.") -> "srv001.acme-inc.com."
        - fqdn("acme-inc.com", "@")                  -> "acme-inc.com."

    Args:
        zone: DNS zone name without trailing dot (recommended).
        name: Record owner name (label, relative name, absolute name, or '@').

    Returns:
        str: Normalized FQDN with trailing dot.
    """
    if name == "@":
        return f"{zone}."  # root of the zone
    if name.endswith("."):
        return name
    if name.endswith(zone):
        return f"{name}."

    return f"{name}.{zone}."


def build_rrset(
    name: str,
    rtype: str,
    ttl: int,
    records: Sequence[RRsetRecordInput],
    changetype: str = "REPLACE",
    comment: Optional[str] = None,
    account: Optional[str] = None,
) -> RRset:
    """
    Build a PowerDNS RRset dictionary for API operations.

    The returned structure is suitable for PowerDNS API payloads (e.g. PATCH with rrsets),
    and has the form:

        {
          "name": "<fqdn.>",
          "type": "<rtype>",
          "ttl": <ttl>,
          "changetype": "<changetype>",
          "records": [{"content": "...", "disabled": False}, ...],
          "comments": [{"content": "...", "account": "..."}]   # only if comment is provided
        }

    Record normalization:
        - If an item in `records` is a string, it is used as `content`.
        - If an item is a mapping, `item["content"]` is used as `content`.

    Args:
        name: RRset owner name. A trailing dot is enforced.
        rtype: Record type (e.g. "A", "AAAA", "CNAME", "MX", "TXT", "SRV", "PTR").
        ttl: Time-to-live in seconds.
        records: Sequence of record inputs (strings or mappings containing a "content" key).
        changetype: PowerDNS change type (typically "REPLACE", "DELETE", "ADD"). Default "REPLACE".
        comment: Optional comment string. If provided, a `comments` section is added.
        account: Optional account value stored alongside the comment (defaults to empty string).

    Returns:
        dict[str, Any]: RRset dictionary (PowerDNS JSON-compatible).

    Raises:
        KeyError: If a mapping in `records` does not contain a "content" key.
        TypeError: If `ttl` is not an int-like value or `records` contains unsupported items.
    """
    rrset: RRset = {
        "name": name if name.endswith(".") else f"{name}.",
        "type": rtype,
        "ttl": int(ttl),
        "changetype": changetype,
        "records": [
            {"content": r if isinstance(r, str) else r["content"], "disabled": False}
            for r in records
        ],
    }

    if comment:
        rrset["comments"] = [
            {
                "content": comment,
                "account": account or "",
            }
        ]

    return rrset
