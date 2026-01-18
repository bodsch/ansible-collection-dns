#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
utils.py

Reverse-zone helper for DNS automation (Ansible context).

This module provides `reverse_zone_names(...)`, a utility that derives the reverse-DNS
domain name for an IPv4 or IPv6 address/network.

Key points:
    - IPv4 inputs return `<reversed octets>.in-addr.arpa` (without trailing dot).
    - IPv6 inputs are processed via `netaddr` and trimmed for CIDR networks to the
      reverse-zone boundary (nibble-based).
    - The function expects an Ansible-like `module` object for logging (`module.log(...)`).

Source: utils.py :contentReference[oaicite:0]{index=0}
"""

from __future__ import absolute_import, print_function

from typing import Any, Optional

import netaddr
from ansible_collections.bodsch.dns.plugins.module_utils.network_type import (
    is_valid_ipv4,
)


def reverse_zone_names(module: Any, network: str) -> Optional[str]:
    """
    Compute the reverse-DNS zone name for an IPv4/IPv6 address or network.

    For IPv4, the reverse name is created by reversing the dotted-quad octets and appending
    ``.in-addr.arpa`` (no trailing dot).

    For IPv6, the function uses `netaddr.IPNetwork` / `netaddr.IPAddress.reverse_dns`. If the input
    is a CIDR network (contains '/'), an offset is derived from the prefix length and the computed
    reverse DNS name is trimmed to match the reverse-zone boundary implied by the prefix.

    Args:
        module: An Ansible-like module object used for logging. Must provide `module.log(...)`.
        network: IPv4/IPv6 address string or CIDR network string (e.g. "192.0.2.10" or "2001:db8::/64").

    Returns:
        Optional[str]:
            - Reverse zone name (without trailing dot) if the input could be processed.
            - None if the input is neither a valid IPv4 nor a valid IPv6 network/address.
    """
    module.log(f"reverse_zone_names({network})")

    result: Optional[str] = None

    if is_valid_ipv4(network):
        reverse_ip = ".".join(network.split(".")[::-1])
        result = f"{reverse_ip}.in-addr.arpa"
        return result

    try:
        offset: Optional[int] = None

        if network.count("/") == 1:
            prefix = network.split("/")[1]
            offset = int(9 + int(prefix) // 2)

        ip_net = netaddr.IPNetwork(str(network))
        ip_addr = netaddr.IPAddress(ip_net)
        reverse_ip = ip_addr.reverse_dns  # usually ends with a trailing "ip6.arpa."

        result = reverse_ip[-offset:] if offset else reverse_ip

        if result.endswith("."):
            result = result[:-1]

    except Exception as e:
        module.log(msg=f" =>  ERROR: {e}")
        result = None

    if not result:
        module.log(
            f" PROBLEM: {network} is neither a valid IPv4 nor a valid IPv6 network."
        )

    return result


def reverse_zone_names_OLD(module, network):
    """ """
    module.log(f"reverse_zone_names({network})")

    # ----------------------------------------------------
    reverse_ip = None

    if is_valid_ipv4(network):

        # module.log(f"

        reverse_ip = ".".join(network.replace(network + ".", "").split(".")[::-1])
        # reverse_ip = ".".join(ip.split(".")[::-1])

        result = f"{reverse_ip}.in-addr.arpa"

    else:
        try:
            _offset = None
            if network.count("/") == 1:
                _prefix = network.split("/")[1]
                _offset = int(9 + int(_prefix) // 2)
                # module.log(msg=f" - {_prefix} - {_offset}")

            _network = netaddr.IPNetwork(str(network))
            _prefix = _network.prefixlen
            _ipaddress = netaddr.IPAddress(_network)
            reverse_ip = _ipaddress.reverse_dns

            if _offset:
                result = reverse_ip[-_offset:]

            if result[-1] == ".":
                result = result[:-1]

        except Exception as e:
            module.log(msg=f" =>  ERROR: {e}")
            pass

    if not result:
        module.log(
            msg=f" PROBLEM: {network} is neither a valid IPv4 nor a valid IPv6 network."
        )

    # module.log(msg=f" = '{result}'")

    return result
