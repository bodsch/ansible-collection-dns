#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2021, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.dns.plugins.module_utils.pihole.pihole import PiHole

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
module: pihole_admin_password
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: TBD
description: TBD

options:
  password:
    description: TBD
    type: str
    required: true

"""

EXAMPLES = r"""

"""

RETURN = """
"""

# ---------------------------------------------------------------------------------------


class PiholeCommand(PiHole):
    """
    """
    module = None

    def __init__(self, module: any):
        """
        """
        self.module = module
        self.command = module.params.get("command")

        super().__init__(module)

    def run(self):
        """
        """
        if self.command == "update_gravity":
            return self.update_gravity()
        if self.command == "reloadlists":
            return self.reload_lists()
        if self.command == "reloaddns":
            return self.reload_dns()


def main():

    argument_spec = dict(
        command=dict(
            default="reloadlists",
            choices=["update_gravity", "reloaddns", "reloadlists"]
        ),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    p = PiholeCommand(module)
    result = p.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
