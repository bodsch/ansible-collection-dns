#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function
import os
import re
import netaddr

from ansible.module_utils.basic import AnsibleModule


class BindZoneData(object):
    """
      Main Class
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self.zone_directory = module.params.get("zone_directory")
        self.zone_data = module.params.get("zone_data")

        self.ipv6 = False

    def run(self):
        """
          runner
        """
        forward_zones = self.define_zone_forward_names()
        reverse_zones = self.define_zone_reverse_names()
        reverse_zones += self.define_zone_reverse_names(ipv6=True)

        self.module.log(msg=f" forward_zones: '{forward_zones}'")
        self.module.log(msg=f" reverse_zones: '{reverse_zones}'")

        forward_data = self.forward_zone_data(forward_zones)
        reverse_data = self.reverse_zone_data(reverse_zones)
        reverse_data = self.reverse_zone_data(reverse_zones)

        result = dict(
            zone_data=dict(
                forward=forward_data,
                reverse=reverse_data
            )
        )

        return result

    def forward_zone_data(self, forward_zones):
        """
        """
        self.module.log(msg=f"forward_zone_data({forward_zones})")
        result = []
        for name in forward_zones:
            self.module.log(msg=f" - '{name}'")

            res = {}
            res[name] = {}

            line, hash, serial = self.read_zone_file(name)

            res[name] = dict(
                filename=str(name),
                # hash=line,
                sha256=str(hash),
                serial=str(serial)
            )

            result.append(res)

        self.module.log(msg=f" = '{result}'")

        return result

    def reverse_zone_data(self, reverse_zones):
        """
        """
        self.module.log(msg=f"reverse_zone_data({reverse_zones})")
        result = []
        for name in reverse_zones:
            self.module.log(msg=f" - '{name}'")
            filename = self.reverse_zone_names(name)

            res = {}
            res[name] = {}

            line, hash, serial = self.read_zone_file(filename)

            res[name] = dict(
                filename=str(filename),
                # hash=line,
                sha256=str(hash),
                serial=str(serial),
                network=str(name)
            )

            result.append(res)

        self.module.log(msg=f" = '{result}'")

        return result

    def read_zone_file(self, zone_file):

        self.module.log(msg=f"read_zone_file({zone_file})")

        line = None
        hash = None
        serial = None
        _file_name = os.path.join(self.zone_directory, zone_file)

        self.module.log(msg=f"'{_file_name}'")

        if os.path.exists(self.zone_directory) and os.path.exists(_file_name):
            with open(os.path.join(self.zone_directory, _file_name), "r") as f:
                zone_data = f.readlines()
                # read first 4 lines from file
                # zone_data = [next(f) for _ in range(14)]

                pattern = re.compile(
                    r'; Hash:.*(?P<hash>[0-9A-Za-z]{64}) (?P<timestamp>[0-9]+)', re.MULTILINE)

                # find regex in list
                # [0]  # Read Note
                _list = list(filter(pattern.match, zone_data))

                if isinstance(_list, list) and len(_list) > 0:
                    line = _list[0].strip()
                    if len(line) > 0:
                        arr = line.split(" ")
                        hash = arr[2]
                        serial = arr[3]

        return (line, hash, serial)

    def define_zone_forward_names(self):
        """
        """
        return [x.get("name") for x in self.zone_data if x.get("state", "present") and x.get("create_reverse_zones", True)]

    def define_zone_reverse_names(self, ipv6=False):
        """
        """
        if not ipv6:
            networks = [x.get("networks") for x in self.zone_data if x.get("state", "present") and x.get("create_reverse_zones", True)]
        else:
            networks = [x.get("ipv6_networks") for x in self.zone_data if x.get("state", "present") and x.get("create_reverse_zones", True)]
        # flatten list of lists
        return [x for row in networks for x in row]

    def define_zone_networks(self):
        """
        """
        networks = [x.get("networks") for x in self.zone_data]
        # flatten list of lists
        return [x for row in networks for x in row]

    def reverse_zone_names(self, network):
        """
        """
        self.module.log(msg=f"reverse_zone_names({network})")

        result = None

        _network = netaddr.IPNetwork(str(network))
        _info = _network.info
        _prefix = _network.prefixlen
        _ipaddress = netaddr.IPAddress(_network)
        self.module.log(msg=f"  ip address: {_ipaddress}")

        result = _ipaddress.reverse_dns

        ipv6 = False
        if _info['IPv6']:
            ipv6 = True

        # self.module.log(msg=f"  - {_info}")
        # self.module.log(msg=f"  - {ipv6}")
        self.module.log(msg=f" = '{result}'")
        if not ipv6:
            result = ".".join(network.replace(
                network + '.', '').split('.')[::-1]) + ".in-addr.arpa"

        if ipv6:
            result = result[-(9 + _prefix // 2):-1]

        self.module.log(msg=f" = '{result}'")

        return result


def main():

    arguments = dict(
        zone_directory=dict(
            required=True,
            type="str"
        ),
        zone_data=dict(
            required=True,
            type="raw"
        ),
    )

    module = AnsibleModule(
        argument_spec=arguments,
        supports_check_mode=True,
    )

    icinga = BindZoneData(module)
    result = icinga.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
