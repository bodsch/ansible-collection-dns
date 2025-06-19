#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2021, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function
import re

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.dns.plugins.module_utils.pihole.pihole import PiHole
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
module: pihole_custom_lists
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: TBD
description: TBD

options:
  allow_list:
    description: TBD
    type: list
    required: false
  deny_list:
    description: TBD
    type: list
    required: false

"""

EXAMPLES = r"""

"""

RETURN = """
"""

# ---------------------------------------------------------------------------------------


class PiholeCustomLists(PiHole):
    """
    """
    module = None

    def __init__(self, module: any):
        """
        """
        self.module = module

        self.allow_list = module.params.get("allow_list")
        self.deny_list = module.params.get("deny_list")

        super().__init__(module)

    def run(self):
        """
        """
        result = dict(
            rc=127,
            failed=True,
            changed=False,
            full_version="unknown"
        )

        if len(self.allow_list) > 0:
            result_allow = self.import_allow_lists(self.allow_list)

        if len(self.deny_list) > 0:
            result_deny = self.import_deny_lists(self.deny_list)


        # _state, _changed, _failed, state, changed, failed = results(self.module, result_state)
        #
        # result = dict(
        #     changed=_changed,
        #     failed=failed,
        #     state=result_state
        # )


def main():

    argument_spec=dict(
        allow_list=dict(
            required=False,
            type="list"
        ),
        deny_list=dict(
            required=False,
            type="list"
        ),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    p = PiholeCustomLists(module)
    result = p.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
