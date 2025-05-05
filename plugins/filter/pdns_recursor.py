# -*- coding: utf-8 -*-
# Copyright 2023-2024 Bodo Schulz <bodo@boone-schulz.de>


# python 3 headers, required if submitting to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.utils.display import Display

# ---------------------------------------------------------------------------------------

display = Display()


class FilterModule(object):
    """
    """

    def filters(self):
        return {
            'recursor_backwards_compatibility': self.recursor_backwards_compatibility,
        }

    def recursor_backwards_compatibility(self, data, version):
        display.v(f"recursor_backwards_compatibility({data}, {version})")

        """
            input:
                ```
                pdns_recursor_recursor:
                  forward_zones:
                    - zone: matrix.lan
                      forwarders:
                        - 192.168.0.4:53
                ```
            output:
                ```
                    [example.org=203.0.113.210]
                ```
        """
        result = []


        return result

