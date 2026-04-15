#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, annotations, division, print_function

import os
import re
from itertools import islice
from typing import Optional, Tuple

import netaddr
from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
module: bind_zone_data
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: TBD
description: TBD

options:
  zone_directory:
    description: []
    type: str
    required: true
  zone_data:
    description: []
    type: raw
    required: true
"""

EXAMPLES = r"""
"""

RETURN = """
"""

# ---------------------------------------------------------------------------------------


class BindZoneData(object):
    """
    Main Class
    """

    module = None

    def __init__(self, module):
        """ """
        self.module = module
        # self.module.log(f"BindZoneData::__init__()")

        self.zone_directory = module.params.get("zone_directory")
        self.zone_data = module.params.get("zone_data")

        self.ipv6 = False

    def run(self):
        """
        runner
        """
        # self.module.log(f"BindZoneData::run()")

        forward_zones = self.define_zone_forward_names()
        reverse_zones = self.define_zone_reverse_names()
        reverse_zones += self.define_zone_reverse_names(ipv6=True)

        # self.module.log(f" forward_zones: '{forward_zones}'")
        # self.module.log(f" reverse_zones: '{reverse_zones}'")

        forward_data = self.forward_zone_data(forward_zones)
        reverse_data = self.reverse_zone_data(reverse_zones)
        # reverse_data = self.reverse_zone_data(reverse_zones)

        result = dict(zone_data=dict(forward=forward_data, reverse=reverse_data))

        return result

    def forward_zone_data(self, forward_zones):
        """ """
        # self.module.log(f"BindZoneData::forward_zone_data(forward_zones: {forward_zones})")

        result = []
        for name in forward_zones:
            # self.module.log(f" - '{name}'")

            res = {}
            res[name] = {}

            hash, serial = self.read_zone_file(name)

            res[name] = dict(filename=str(name), sha256=str(hash), serial=str(serial))

            result.append(res)

        return result

    def reverse_zone_data(self, reverse_zones):
        """ """
        # self.module.log(f"BindZoneData::reverse_zone_data(reverse_zones: {reverse_zones})")

        result = []
        for name in reverse_zones:
            self.module.log(f" - '{name}'")

            filename = self.reverse_zone_names(name)

            res = {}
            res[name] = {}

            hash, serial = self.read_zone_file(filename)

            res[name] = dict(
                filename=str(filename),
                sha256=str(hash),
                serial=str(serial),
                network=str(name),
            )

            result.append(res)

        return result

    def read_zone_file(self, zone_file: str) -> Tuple[Optional[str], Optional[str]]:
        """Read the zone file header and extract stored hash and serial.

        The function reads up to the first five lines of the zone file and looks
        for a comment line containing the persisted hash and serial value.

        Args:
            zone_file: Relative zone file name inside the configured zone directory.

        Returns:
            A tuple containing:
                - The extracted SHA-256 hash as a string, or None
                - The extracted serial as a string, or None
        """
        # self.module.log(f"BindZoneData::read_zone_file(zone_file: {zone_file})")

        zone_hash: Optional[str] = None
        serial: Optional[str] = None
        file_name = os.path.join(self.zone_directory, zone_file)

        pattern = re.compile(
            r"^;\s*Hash:.*?(?P<hash>[0-9A-Fa-f]{64})\s+(?P<serial>[0-9]+)\s*$"
        )

        if not os.path.exists(file_name):
            # self.module.log(f"file {file_name} not exists.")
            # self.module.log(f"= hash: {zone_hash}, serial: {serial}")
            return zone_hash, serial

        try:
            with open(file_name, "r", encoding="utf-8") as file_handle:
                zone_data = [line.rstrip("\n") for line in islice(file_handle, 5)]
                # self.module.log(f"  - header lines: {zone_data}")

            for line in zone_data:
                match = pattern.match(line.strip())
                if match:
                    zone_hash = match.group("hash")
                    serial = match.group("serial")
                    break

        except OSError as exc:
            self.module.log(f"failed to read zone file {file_name}: {exc}")

        return zone_hash, serial

    def read_zone_file_OLD(self, zone_file):
        """ """
        self.module.log(f"BindZoneData::read_zone_file(zone_file: {zone_file})")

        # line = None
        hash = None
        serial = None
        _file_name = os.path.join(self.zone_directory, zone_file)

        # self.module.log(f"   zone_directory: '{self.zone_directory}'")
        # self.module.log(f"   zone_file     : '{zone_file}'")
        # self.module.log(f"   file_name     : '{_file_name}'")
        # self.module.log(f"                 : '{os.path.join(self.zone_directory, _file_name)}'")

        if os.path.exists(_file_name):
            with open(_file_name, "r") as f:
                # zone_data = f.readlines()
                # read first 4 lines from file
                zone_data = [next(f) for _ in range(5)]
                self.module.log(f"                 : {zone_data}")

                pattern = re.compile(
                    r"; Hash:.*(?P<hash>[0-9A-Za-z]{64}) (?P<timestamp>[0-9]+)",
                    re.MULTILINE,
                )

                # find regex in list
                # [0]  # Read Note
                _list = list(filter(pattern.match, zone_data))

                self.module.log(f"  - list: {_list}")

                if isinstance(_list, list) and len(_list) > 0:
                    line = _list[0].strip()
                    if len(line) > 0:
                        arr = line.split(" ")
                        hash = arr[2]
                        serial = arr[3]
        else:
            self.module.log(f"file {_file_name} not exists.")

        self.module.log(f"= hash: {hash}, serial: {serial}")

        return (hash, serial)

    def define_zone_forward_names(self):
        """ """
        # self.module.log("BindZoneData::define_zone_forward_names()")

        return [
            x.get("name")
            for x in self.zone_data
            if x.get("state", "present") and x.get("create_forward_zones", True)
        ]

    def define_zone_reverse_names(self, ipv6=False):
        """ """
        # self.module.log("BindZoneData::define_zone_reverse_names({ipv6})")

        networks = []

        if not ipv6:
            networks = [
                x.get("networks", [])
                for x in self.zone_data
                if x.get("state", "present") and x.get("create_reverse_zones", True)
            ]
        else:
            networks = [
                x.get("ipv6_networks", [])
                for x in self.zone_data
                if x.get("state", "present") and x.get("create_reverse_zones", True)
            ]

        # self.module.log(f" - {networks} (type(networks))")
        if networks:
            # flatten list of lists
            networks = [x for row in networks for x in row]
        else:
            networks = []

        # self.module.log(f" = {networks}")
        return networks

    def define_zone_networks(self):
        """ """
        # self.module.log("BindZoneData::define_zone_networks()")

        networks = [x.get("networks") for x in self.zone_data]
        # flatten list of lists
        return [x for row in networks for x in row]

    def reverse_zone_names(self, network):
        """ """
        # self.module.log(f"BindZoneData::reverse_zone_names(network: {network})")

        # ----------------------------------------------------
        from ansible_collections.bodsch.dns.plugins.module_utils.network_type import (
            is_valid_ipv4,
        )

        reverse_ip = None

        if is_valid_ipv4(network):
            reverse_ip = ".".join(network.replace(network + ".", "").split(".")[::-1])
            # reverse_ip = ".".join(ip.split(".")[::-1])

            result = f"{reverse_ip}.in-addr.arpa"

        else:
            try:
                _offset = None
                if network.count("/") == 1:
                    _prefix = network.split("/")[1]
                    _offset = int(9 + int(_prefix) // 2)
                    # self.module.log(f" - {_prefix} - {_offset}")

                _network = netaddr.IPNetwork(str(network))
                _prefix = _network.prefixlen
                _ipaddress = netaddr.IPAddress(_network)
                reverse_ip = _ipaddress.reverse_dns

                if _offset:
                    result = reverse_ip[-_offset:]

                if result[-1] == ".":
                    result = result[:-1]

            except Exception as e:
                self.module.log(f" =>  ERROR: {e}")
                pass

        if not result:
            self.module.log(
                msg=f" PROBLEM: {network} is neither a valid IPv4 nor a valid IPv6 network."
            )

        # self.module.log(f" = '{result}'")

        return result


def main():

    arguments = dict(
        zone_directory=dict(required=True, type="str"),
        zone_data=dict(required=True, type="raw"),
    )

    module = AnsibleModule(
        argument_spec=arguments,
        supports_check_mode=True,
    )

    zone_data = BindZoneData(module)
    result = zone_data.run()

    # module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
