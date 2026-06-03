#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

from typing import Any, Callable

from ansible.utils.display import Display
from ansible_collections.bodsch.core.plugins.module_utils.dns_lookup import (
    DNSLookupResult,
    dns_lookup,
)

display: Display = Display()


class FilterModule(object):
    def filters(self) -> dict[str, Callable[..., Any]]:
        return {"dns_lookup": self.lookup}

    def lookup(self, data, timeout=3, dns_resolvers=["9.9.9.9"]) -> DNSLookupResult:
        """
        use a simple DNS lookup, return results in a dictionary

        similar to
        {'addrs': [], 'error': True, 'error_msg': 'No such domain instance', 'name': 'instance'}
        """
        display.vvv(
            f"bodsch.dns.dns_lookup(data: {data}, timeout: {timeout}, dns_resolvers: {dns_resolvers})"
        )

        result: DNSLookupResult = dns_lookup(data, timeout, dns_resolvers)

        display.vvv(f"= return : {result}")

        return result
