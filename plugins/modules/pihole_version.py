#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2024-2025, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.dns.plugins.module_utils.pihole.pihole import PiHole

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
module: pihole_version
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: return the version of installed pihole
description: return the version of installed pihole

options:
  validate_version:
    description: check against the installed version.
    type: str
    required: false

"""

EXAMPLES = r"""
- name: detect pihole version
  become: true
  bodsch.dns.pihole_version:
  register: pihole_version
  check_mode: false
  ignore_errors: true

- name: detect pihole version
  become: true
  bodsch.dns.pihole_version:
    validate_version: '9.18.0'
  register: pihole_version
  check_mode: false
  ignore_errors: true
"""

RETURN = """
"""

# ---------------------------------------------------------------------------------------


class PiholeVersion(PiHole):
    """
    Main Class
    """

    module = None

    def __init__(self, module):
        """ """
        self.module = module

        super().__init__(module)

        self.validate_version = module.params.get("validate_version")

    def run(self):
        """
        """
        version: dict = self.version()

        # self.module.log(f"  version: {version}")

        if self.validate_version:
            if version.get("full_version") == self.validate_version:
                _failed = False
                msg = f"version {self.validate_version} successful installed."
            else:
                _failed = True
                msg = f"version {self.validate_version} not installed."
        else:
            _failed = False
            msg = "pihole is installed."

        version["failed"] = _failed
        version["msg"] = msg

        return version


# ===========================================
# Module execution.
#


def main():

    arguments = dict(validate_version=dict(required=False, type="str"))

    module = AnsibleModule(
        argument_spec=arguments,
        supports_check_mode=True,
    )

    r = PiholeVersion(module)
    result = r.run()

    # module.log(msg="= result: {}".format(result))

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
