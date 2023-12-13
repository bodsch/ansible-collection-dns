#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function
import os
import re

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
        self.reverse_zone = module.params.get("reverse_zone")
        self.networks = module.params.get("networks")

        self.module.log(msg=f"{self.networks}")

    def run(self):
        """
          runner
        """
        _hash = []

        _file_name = os.path.join(self.zone_directory, self.zone_file)

        self.module.log(msg=f"'{_file_name}'")

        if os.path.exists(self.zone_directory) and os.path.exists(_file_name):
            with open(os.path.join(self.zone_directory, self.zone_file), "r") as f:
                # read first 4 lines from file
                zone_data = f.readlines()
                # zone_data = [next(f) for _ in range(14)]

                self.module.log(msg=f" - '{zone_data}'")

                pattern = re.compile(r'; Hash:.*(?P<hash>[0-9A-Za-z]{64}) (?P<timestamp>[0-9]+)', re.MULTILINE)

                # find regex in list
                _list = list(filter(pattern.match, zone_data))  # [0]  # Read Note

                self.module.log(msg=f" => '{_list}'")

                if isinstance(_list, list) and len(_list) > 0:
                    line = _list[0].strip()

                    #self.module.log(msg=f" -> '{line}'")
                    #hash = line.split(" ")[2]
                    #self.module.log(msg=f" -> '{hash}'")

                    if not self.reverse_zone:
                        _hash.append(
                            dict(
                                name=self.zone_file,
                                hash=line
                            )
                        )
                    else:
                        _hash.append(
                            dict(
                                name=self.zone_file,
                                hash=line,
                                network=self.networks
                            )
                        )

        result = dict(
            failed=False,
            changed=False,
            hash=_hash
        )

        return result


def main():

    arguments = dict(
        zone_directory=dict(
            required=True,
            type="str"
        ),
        zone_file=dict(
            required=True,
            type="str"
        ),
        reverse_zone=dict(
            required=False,
            type="bool",
            default=False
        ),
        networks=dict(
            required=False,
            type="raw"
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
