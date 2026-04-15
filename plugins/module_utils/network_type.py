#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
network_type.py

IP address and reverse-DNS helper functions.

This module provides:
    - `reverse_dns(...)`: Convert an IPv4/IPv6 address (optionally a CIDR network) into its
      corresponding reverse-DNS domain name.
    - `is_valid_ipv4(...)`: Validate whether a string is a syntactically valid IPv4 address
      (supports dotted, decimal, octal, hex notations per the used regex).
    - `is_valid_ipv6(...)`: Validate whether a string is a syntactically valid IPv6 address.

Implementation notes:
    - IPv6 reverse computation uses `netaddr.IPNetwork` / `netaddr.IPAddress`.
    - For IPv6 CIDR inputs, an offset is applied so the returned reverse name corresponds to the
      reverse-zone boundary implied by the prefix length.
    - `reverse_dns(...)` logs an error and returns `None` if the input cannot be interpreted
      as a valid IPv4 or IPv6 address/network.

Source: `network_type.py` :contentReference[oaicite:0]{index=0}
"""

from __future__ import absolute_import, print_function

import logging
import re
from typing import Optional

import netaddr

__metaclass__ = type

logging.basicConfig(level=logging.DEBUG)


def reverse_dns(data: str) -> Optional[str]:
    """
    Convert an IP address (IPv4/IPv6) or network (CIDR) into its reverse-DNS name.

    Behavior:
        - If `data` is a valid IPv4 address, the function returns:
              "<reversed octets>.in-addr.arpa"
          Example:
              "192.0.2.10" -> "10.2.0.192.in-addr.arpa"

        - Otherwise, the function tries to parse `data` as an IPv6 address or IPv6 network via
          `netaddr.IPNetwork`. If parsing succeeds, it uses `IPAddress(...).reverse_dns` and, for CIDR
          inputs, trims the result to match the reverse-zone boundary implied by the prefix length.

        - If parsing fails, the function logs an error and returns `None`.

    Args:
        data: IPv4/IPv6 address string or CIDR network string (e.g. "2001:db8::/64").

    Returns:
        Optional[str]:
            - Reverse-DNS domain name (without a trailing dot) on success.
            - None if the input is not a valid IPv4/IPv6 address/network.
    """
    reverse_ip: Optional[str] = None
    result: Optional[str] = None

    if is_valid_ipv4(data):
        # Reverse octets for in-addr.arpa.
        reverse_ip = ".".join(data.split(".")[::-1])
        result = f"{reverse_ip}.in-addr.arpa"
    else:
        try:
            offset: Optional[int] = None
            if data.count("/") == 1:
                prefix_str = data.split("/")[1]
                # Original logic: compute an offset depending on prefix.
                offset = int(9 + int(prefix_str) // 2)

            network = netaddr.IPNetwork(str(data))
            ipaddress = netaddr.IPAddress(network)
            reverse_ip = (
                ipaddress.reverse_dns
            )  # typically ends with a trailing "ip6.arpa."

            if offset:
                result = reverse_ip[-offset:]
            else:
                result = reverse_ip

            if result and result.endswith("."):
                result = result[:-1]

        except Exception:
            # Keep original behavior: swallow parsing errors and handle below.
            pass

    if not result:
        logging.error(
            f"PROBLEM: {data} is neither a valid IPv4 nor a valid IPv6 network."
        )
        return None

    # logging.info(f"= {result}")
    return result


def is_valid_ipv4(ip: str) -> bool:
    """
    Validate whether a string is a syntactically valid IPv4 address.

    The regex supports multiple IPv4 notations:
        - dotted decimal/octal/hex variants
        - pure decimal/octal/hex integer forms

    Args:
        ip: IPv4 address candidate string.

    Returns:
        bool: True if `ip` matches the IPv4 pattern, otherwise False.
    """
    pattern = re.compile(
        r"""
        ^
        (?:
          # Dotted variants:
          (?:
            # Decimal 1-255 (no leading 0's)
            [3-9]\d?|2(?:5[0-5]|[0-4]?\d)?|1\d{0,2}
          |
            0x0*[0-9a-f]{1,2}  # Hexadecimal 0x0 - 0xFF (possible leading 0's)
          |
            0+[1-3]?[0-7]{0,2} # Octal 0 - 0377 (possible leading 0's)
          )
          (?:                  # Repeat 0-3 times, separated by a dot
            \.
            (?:
              [3-9]\d?|2(?:5[0-5]|[0-4]?\d)?|1\d{0,2}
            |
              0x0*[0-9a-f]{1,2}
            |
              0+[1-3]?[0-7]{0,2}
            )
          ){0,3}
        |
          0x0*[0-9a-f]{1,8}    # Hexadecimal notation, 0x0 - 0xffffffff
        |
          0+[0-3]?[0-7]{0,10}  # Octal notation, 0 - 037777777777
        |
          # Decimal notation, 1-4294967295:
          429496729[0-5]|42949672[0-8]\d|4294967[01]\d\d|429496[0-6]\d{3}|
          42949[0-5]\d{4}|4294[0-8]\d{5}|429[0-3]\d{6}|42[0-8]\d{7}|
          4[01]\d{8}|[1-3]\d{0,9}|[4-9]\d{0,8}
        )
        $
    """,
        re.VERBOSE | re.IGNORECASE,
    )

    return pattern.match(ip) is not None


def is_valid_ipv6(ip: str) -> bool:
    """
    Validate whether a string is a syntactically valid IPv6 address.

    The regex accepts:
        - full and compressed IPv6 forms (single '::')
        - IPv4-mapped tail forms (ending in dotted IPv4)

    Args:
        ip: IPv6 address candidate string.

    Returns:
        bool: True if `ip` matches the IPv6 pattern, otherwise False.
    """
    pattern = re.compile(
        r"""
        ^
        \s*                         # Leading whitespace
        (?!.*::.*::)                # Only a single wildcard allowed
        (?:(?!:)|:(?=:))            # Colon iff it would be part of a wildcard
        (?:                         # Repeat 6 times:
            [0-9a-f]{0,4}           #   A group of at most four hexadecimal digits
            (?:(?<=::)|(?<!::):)    #   Colon unless preceeded by wildcard
        ){6}                        #
        (?:                         # Either
            [0-9a-f]{0,4}           #   Another group
            (?:(?<=::)|(?<!::):)    #   Colon unless preceeded by wildcard
            [0-9a-f]{0,4}           #   Last group
            (?: (?<=::)             #   Colon iff preceeded by exactly one colon
             |  (?<!:)              #
             |  (?<=:) (?<!::) :    #
             )                      # OR
         |                          #   A v4 address with NO leading zeros
            (?:25[0-4]|2[0-4]\d|1\d\d|[1-9]?\d)
            (?: \.
                (?:25[0-4]|2[0-4]\d|1\d\d|[1-9]?\d)
            ){3}
        )
        \s*                         # Trailing whitespace
        $
    """,
        re.VERBOSE | re.IGNORECASE | re.DOTALL,
    )

    return pattern.match(ip) is not None
