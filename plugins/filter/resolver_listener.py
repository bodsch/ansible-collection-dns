# -*- coding: utf-8 -*-
# Copyright 2023-2024 Bodo Schulz <bodo@boone-schulz.de>

# BSD 2-clause (see LICENSE or https://opensource.org/licenses/BSD-2-Clause)

"""
filter plugin file for knot_resolver filters: resolver_listener
"""


# python 3 headers, required if submitting to Ansible
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.utils.display import Display

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
name: resolver_listener
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

description: TBD
short_description: TBD

"""

EXAMPLES = """
"""

RETURN = """
"""

# ---------------------------------------------------------------------------------------


display = Display()


class FilterModule(object):
    """ """

    def filters(self):
        return {
            "resolver_listener": self.listener,
        }

    def listener(self, data):
        """ """
        result = ""
        # count = len(data)
        # display.v("found: {} entries in {} {}".format(count, data, type(data)))

        if isinstance(data, dict):
            _interfaces = []
            _ips = []
            _port = 0
            _options = []

            interfaces = data.get("interfaces", [])
            ips = data.get("ips", [])
            port = data.get("port", "")
            options = data.get("options", {})

            if len(interfaces) > 0:
                _interfaces = ("net." + ",net.".join(interfaces)).split(",")

            if len(ips) > 0:
                _ips = ("'" + "','".join(ips) + "'").split(",")

            if int(port) > 0:
                _port = [str(port)]

            if len(options) > 0:
                for k, v in options.items():
                    # -- {{ k }} - {{ v }}
                    if k.lower() == "tls" and v:
                        _options = ["{ tls = true }"]
                    elif k.lower() == "kind" and v:
                        _options = [f"{{ {k.lower()} = '{v}' }}"]

            _listen = ["{ " + ", ".join(_interfaces + _ips) + " }"]
            result = ", ".join(_listen + _port + _options)

            # display.v("result {} {}".format(result, type(result)))

            return result
