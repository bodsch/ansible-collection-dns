#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)

import re
import netaddr
import logging

# from dns.resolver import Resolver
# import dns.exception

__metaclass__ = type

logging.basicConfig(level=logging.DEBUG)


def reverse_dns(data):
    """
    """
    # logging.info(f"__reverse_dns({data})")

    reverse_ip = None
    result = None

    # display.v(f"__reverse_dns({data})")
    if is_valid_ipv4(data):
        reverse_ip = ".".join(data.replace(data + '.', '').split('.')[::-1])
        result = f"{reverse_ip}.in-addr.arpa"

    else:
        try:
            _offset = None
            if data.count("/") == 1:
                _prefix = data.split("/")[1]
                _offset = int(9 + int(_prefix) // 2)
                # display.v(f" {_prefix} - {_offset}")

            _network = netaddr.IPNetwork(str(data))
            _prefix = _network.prefixlen
            _ipaddress = netaddr.IPAddress(_network)
            reverse_ip = _ipaddress.reverse_dns

            if _offset:
                result = reverse_ip[-_offset:]

            if result[-1] == ".":
                result = result[:-1]

            # logging.info(f" - {reverse_ip}")
            # logging.info(f" - {result}")

            # return result

        except Exception:
            # display.v(f" ERROR: {e}")
            pass

    if not result:
        logging.error(f" PROBLEM: {data} is neither a valid IPv4 nor a valid IPv6 network.")

    logging.info(f" = {result}")

    return result


def is_valid_ipv4(ip):
    """
        Validates IPv4 addresses.
    """
    pattern = re.compile(r"""
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
    """, re.VERBOSE | re.IGNORECASE)

    return pattern.match(ip) is not None


def is_valid_ipv6(ip):
    """
        Validates IPv6 addresses.
    """
    pattern = re.compile(r"""
        ^
        \s*                         # Leading whitespace
        (?!.*::.*::)                # Only a single whildcard allowed
        (?:(?!:)|:(?=:))            # Colon iff it would be part of a wildcard
        (?:                         # Repeat 6 times:
            [0-9a-f]{0,4}           #   A group of at most four hexadecimal digits
            (?:(?<=::)|(?<!::):)    #   Colon unless preceeded by wildcard
        ){6}                        #
        (?:                         # Either
            [0-9a-f]{0,4}           #   Another group
            (?:(?<=::)|(?<!::):)    #   Colon unless preceeded by wildcard
            [0-9a-f]{0,4}           #   Last group
            (?: (?<=::)             #   Colon iff preceeded by exacly one colon
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
    """, re.VERBOSE | re.IGNORECASE | re.DOTALL)

    return pattern.match(ip) is not None
