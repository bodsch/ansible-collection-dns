#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
dns_lookup.py

Simple DNS lookup helpers built on top of `dnspython` (dns.resolver.Resolver).

This module exposes:
    - `dns_lookup(...)`: resolve a DNS name to its addresses, using either the
      system resolver configuration or an explicitly provided nameserver list.
    - `zone_soa_serial(...)`: query the SOA serial of a zone (used for change
      detection), optionally against a specific authoritative server.

Behavior of `dns_lookup`:
    - Returns a consistent result dictionary with:
        - `name`: the requested DNS name
        - `addrs`: a list of resolved IP addresses (A/AAAA depending on resolver defaults)
        - `error`: boolean error flag
        - `error_msg`: textual error description (empty on success)
    - Handles common resolver failures such as NXDOMAIN, timeout, and missing nameservers.

Notes:
    - `dns_resolvers` should contain IP addresses of recursive resolvers (nameservers).
    - `dns_resolvers` defaults to `None` (system resolver) to avoid mutable-default pitfalls.
"""

from __future__ import absolute_import, annotations

from typing import TypedDict

import dns.exception
import dns.message
import dns.query
import dns.rdatatype
import dns.resolver
from dns.resolver import Answer, Resolver


class DNSLookupResult(TypedDict):
    """
    Result structure returned by `dns_lookup`.

    Keys:
        name: The queried DNS name (may be empty/None if caller passed it).
        addrs: List of resolved IP addresses.
        error: True if the lookup failed, otherwise False.
        error_msg: Error message; empty string on success.
    """

    name: str | None
    addrs: list[str]
    error: bool
    error_msg: str


def _result(
    dns_name: str | None,
    addrs: list[str] | None = None,
    error_msg: str = "",
) -> DNSLookupResult:
    """Build a `DNSLookupResult`.

    The `error` flag is derived from `error_msg`: a non-empty message marks a
    failure, an empty one a success.
    """
    return DNSLookupResult(
        name=dns_name,
        addrs=addrs or [],
        error=bool(error_msg),
        error_msg=error_msg,
    )


def dns_lookup(
    dns_name: str | None,
    timeout: int | float = 3,
    dns_resolvers: list[str] | None = None,
) -> DNSLookupResult:
    """
    Perform a DNS lookup for `dns_name` and return a structured result.

    The function uses `dnspython`'s `Resolver.resolve()` and returns the `address`
    attribute of each response record.

    Args:
        dns_name: DNS name to resolve (e.g. "example.com"). If falsy, an error result is returned.
        timeout: Timeout in seconds applied to both `resolver.timeout` and `resolver.lifetime`.
        dns_resolvers: Optional list of resolver IP addresses to use as nameservers. If omitted
            or empty, system resolver configuration is used.

    Returns:
        DNSLookupResult: A dictionary with the following keys:
            - name (Optional[str]): The requested DNS name.
            - addrs (list[str]): List of resolved IP addresses. Empty on failures.
            - error (bool): True if resolution failed, otherwise False.
            - error_msg (str): Error description (empty string on success).

    Exceptions handled:
        - dns.resolver.NXDOMAIN: "No such domain"
        - dns.resolver.NoNameservers: stringified exception in `error_msg`
        - dns.resolver.Timeout: "Timed out while resolving"
        - dns.exception.DNSException: "Unhandled exception (...)" for any other dnspython errors
    """
    if not dns_name:
        return _result(dns_name, error_msg="No DNS Name for resolving given")

    resolver: Resolver = Resolver()
    resolver.timeout = float(timeout)
    resolver.lifetime = float(timeout)

    if dns_resolvers:
        resolver.nameservers = dns_resolvers

    try:
        records: Answer = resolver.resolve(qname=dns_name)
        return _result(dns_name, addrs=[ii.address for ii in records])
    except dns.resolver.NXDOMAIN:
        return _result(dns_name, error_msg="No such domain")
    except dns.resolver.NoNameservers as e:
        return _result(dns_name, error_msg=repr(e))
    except dns.resolver.Timeout:
        return _result(dns_name, error_msg="Timed out while resolving")
    except dns.exception.DNSException as e:
        return _result(dns_name, error_msg=f"Unhandled exception ({repr(e)})")


def zone_soa_serial(
    zone: str | None,
    nameserver: str | None = None,
    port: int = 53,
    timeout: int | float = 3,
) -> int | None:
    """Return the SOA serial of a zone, or None if it cannot be determined.

    Uses `dnspython` directly (no external tools). When `nameserver` is given
    the zone's authoritative server is queried directly, so the answer reflects
    the authoritative serial rather than a cached one; otherwise the system
    resolver configuration is used.

    Args:
        zone: Zone name to query the SOA for (e.g. "example.com").
        nameserver: Optional IP of the server to query directly.
        port: Port of the nameserver to query (default: 53).
        timeout: Timeout in seconds for the query.

    Returns:
        The SOA serial as int, or None on any failure / missing answer.
    """
    if not zone:
        return None

    try:
        if nameserver:
            query = dns.message.make_query(zone, dns.rdatatype.SOA)
            response = dns.query.udp(
                query, nameserver, port=int(port), timeout=float(timeout)
            )
            answer = response.answer
        else:
            resolver = Resolver()
            resolver.timeout = float(timeout)
            resolver.lifetime = float(timeout)
            answer = resolver.resolve(zone, dns.rdatatype.SOA).response.answer

        for rrset in answer:
            for item in rrset:
                if item.rdtype == dns.rdatatype.SOA:
                    return int(item.serial)
    except dns.exception.DNSException:
        return None

    return None
