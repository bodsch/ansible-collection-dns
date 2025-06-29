#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2021, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.dns.plugins.module_utils.pihole.config import ConfigManager
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


class PiHoleConfig(ConfigManager):
    """
    """
    module = None

    def __init__(self, module: any):
        """
        """
        self.module = module

        self.config = module.params.get("config")

        super().__init__(module)

    def run(self):
        """
        """
        result = dict(
            rc=127,
            failed=True,
            changed=False,
            msg="unknown"
        )

        result_state = self.set_config(config=self.config)

        _state, _changed, _failed, state, changed, failed = results(self.module, result_state)

        result = dict(
            changed=_changed,
            failed=failed,
            state=result_state
        )

        return result


def main():

    argument_spec = dict(
        config=dict(
            required=True,
            type="dict"
        ),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    p = PiHoleConfig(module)
    result = p.run()

    # module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
