# -*- coding: utf-8 -*-
# Copyright 2023-2024 Bodo Schulz <bodo@boone-schulz.de>


# python 3 headers, required if submitting to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.test.core import version_compare
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
        """
            input:
                ```
                pdns_recursor_recursor:
                  forward_zones:
                    - zone: matrix.lan
                      forwarders:
                        - 192.168.0.4:53
                        - 192.168.0.1:5300
                    - zone: google.de
                      forwarders:
                        - 127.0.0.1
                    - zone: google.com
                      forwarders:
                        - 127.0.0.1
                ```
            output:
                ```
                    ['matrix.lan=192.168.0.4;192.168.0.1:5300', 'google.de=127.0.0.1', 'google.com=127.0.0.1']
                ```
        """
        # display.v(f"recursor_backwards_compatibility({data}, {version})")
        result = []

        if version_compare(str(version), '5', '>='):
            return data

        for i in data:
            zone = i.get('zone')
            forwarders = ";".join(i.get('forwarders', []))
            result.append(f"{zone}={forwarders}")

        return result
