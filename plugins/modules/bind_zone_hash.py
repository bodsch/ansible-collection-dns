#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function
import os
import re
import netaddr

from ansible.module_utils.basic import AnsibleModule


class BindZoneHash(object):
    """
      Main Class
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self.zone_directory = module.params.get("zone_directory")
        self.zone_file = module.params.get("zone_file")
        self.zone_data = module.params.get("zone_data")
        self.reverse_zone = module.params.get("reverse_zone")
        self.networks = module.params.get("networks")
        self.ipv6 = module.params.get("ipv6")

        # self.module.log(msg=f"{self.networks}")

    def run(self):
        """
          runner
        """
        _hash = []

        if self.reverse_zone:
            zone_files = self.define_zone_networks()
        else:
            zone_files = self.define_zone_names()

        for name in zone_files:
            self.module.log(msg=f" - '{name}'")

            if self.reverse_zone:
                network = name
                name = self.reverse_zone_names(name)

            line = self.read_zone_file(name)

            if not self.reverse_zone:
                _hash.append(
                    dict(
                        name=str(name),
                        hash=line
                    )
                )
            else:
                _hash.append(
                    dict(
                        name=str(name),
                        hash=line,
                        network=str(network)
                    )
                )

        self.module.log(msg=f" = '{_hash}'")

        result = dict(
            failed=False,
            changed=False,
            hash=_hash
        )

        return result

    def read_zone_file(self, zone_file):

        self.module.log(msg=f"read_zone_file({zone_file})")

        line = None
        _file_name = os.path.join(self.zone_directory, zone_file)

        self.module.log(msg=f"'{_file_name}'")

        if os.path.exists(self.zone_directory) and os.path.exists(_file_name):
            with open(os.path.join(self.zone_directory, _file_name), "r") as f:
                # read first 4 lines from file
                zone_data = f.readlines()
                # zone_data = [next(f) for _ in range(14)]

                self.module.log(msg=f" - '{zone_data}'")

                pattern = re.compile(
                    r'; Hash:.*(?P<hash>[0-9A-Za-z]{64}) (?P<timestamp>[0-9]+)', re.MULTILINE)

                # find regex in list
                # [0]  # Read Note
                _list = list(filter(pattern.match, zone_data))

                self.module.log(msg=f" => '{_list}'")

                if isinstance(_list, list) and len(_list) > 0:
                    line = _list[0].strip()

        return line

        #             #self.module.log(msg=f" -> '{line}'")
        #             #hash = line.split(" ")[2]
        #             #self.module.log(msg=f" -> '{hash}'")
        #
        #             if not self.reverse_zone:
        #                 _hash.append(
        #                     dict(
        #                         name=self.zone_file,
        #                         hash=line
        #                     )
        #                 )
        #             else:
        #                 _hash.append(
        #                     dict(
        #                         name=self.zone_file,
        #                         hash=line,
        #                         network=self.networks
        #                     )
        #                 )
        #
        # result = dict(
        #     failed=False,
        #     changed=False,
        #     hash=_hash
        # )
        #
        # return result

    def define_zone_names(self):
        """
        """
        return [x.get("name") for x in self.zone_data]

    def define_zone_networks(self):
        """
        """
        networks = [x.get("networks") for x in self.zone_data]
        # flatten list of lists
        return [x for row in networks for x in row]

    def reverse_zone_names(self, network):
        """
        """
        result = None
        # create reverse names
        if not self.ipv6:
            result = ".".join(network.replace(
                network + '.', '').split('.')[::-1]) + ".in-addr.arpa"
        else:
            # (item.1 | ansible.utils.ipaddr('revdns'))[-(9+(item.1|regex_replace('^.*/','')|int)//2):-1] }}
            _network = netaddr.IPNetwork(str(network))
            _ipaddress = netaddr.IPAddress(_network)
            result = _ipaddress.reverse_dns
            pass

        self.module.log(msg=f" = '{result}'")

        return result


def main():

    arguments = dict(
        zone_directory=dict(
            required=True,
            type="str"
        ),
        zone_file=dict(
            required=False,
            type="str"
        ),
        zone_data=dict(
            required=True,
            type="raw"
        ),
        reverse_zone=dict(
            required=False,
            type="bool",
            default=False
        ),
        networks=dict(
            required=False,
            type="raw"
        ),
        ipv6=dict(
            default=False,
            type="bool"
        )
    )

    module = AnsibleModule(
        argument_spec=arguments,
        supports_check_mode=True,
    )

    icinga = BindZoneHash(module)
    result = icinga.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
