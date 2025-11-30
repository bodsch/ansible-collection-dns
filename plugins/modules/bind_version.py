#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2021, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import re

from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
module: bind_version
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: return the version of installed bind
description: return the version of installed bind

options:
  validate_version:
    description: check against the installed version.
    type: str
    required: false

"""

EXAMPLES = r"""
- name: detect bind version
  become: true
  bodsch.dns.bind_version:
  register: bind_version
  check_mode: false
  ignore_errors: true

- name: detect bind version
  become: true
  bodsch.dns.bind_version:
    validate_version: '9.18.0'
  register: bind_version
  check_mode: false
  ignore_errors: true
"""

RETURN = """
"""

# ---------------------------------------------------------------------------------------


class BindVersion(object):
    """
    Main Class
    """

    module = None

    def __init__(self, module):
        """
        Initialize all needed Variables
        """
        self.module = module

        self.validate_version = module.params.get("validate_version")
        self.named_bin = module.get_bin_path("named", False)

    def run(self):
        """
        runner
        """
        result = dict(rc=127, failed=True, changed=False, full_version="unknown")

        if not self.named_bin:
            return dict(rc=0, failed=False, changed=False, msg="no named installed")

        rc, out, err = self._exec(["-v"])

        if rc == 0:
            _failed = True
            msg = "unknown message"

            #
            # named -v
            # BIND 9.18.19-1~deb12u1-Debian (Extended Support Version) <id:>
            pattern = re.compile(
                r"^BIND (?P<version>(?P<major>\d+).(?P<minor>\d+).(?P<patch>\*|\d+)).*"
            )
            version = re.search(pattern, out)
            if version:
                version_full_string = version.group("version")
                version_major_string = version.group("major")
                version_minor_string = version.group("minor")
                version_patch_string = version.group("patch")

            if self.validate_version:
                if version_full_string == self.validate_version:
                    _failed = False
                    msg = f"version {self.validate_version} successful installed."
                else:
                    _failed = True
                    msg = f"version {self.validate_version} not installed."
            else:
                _failed = False
                msg = "named is installed."

            result = dict(
                failed=_failed,
                rc=0,
                msg=msg,
                full_version=version_full_string,
                version=dict(
                    major=int(version_major_string),
                    minor=int(version_minor_string),
                    patch=int(version_patch_string),
                ),
                excutable=self.named_bin,
            )

        return result

    def _exec(self, args):
        """ """
        cmd = [self.named_bin] + args

        rc, out, err = self.module.run_command(cmd, check_rc=True)
        # self.module.log(msg="  rc : '{}'".format(rc))
        # self.module.log(msg="  out: '{}' ({})".format(out, type(out)))
        # self.module.log(msg="  err: '{}'".format(err))
        return rc, out, err


# ===========================================
# Module execution.
#


def main():

    module = AnsibleModule(
        argument_spec=dict(validate_version=dict(required=False, type="str")),
        supports_check_mode=True,
    )

    icinga = BindVersion(module)
    result = icinga.run()

    module.log(msg="= result: {}".format(result))

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
