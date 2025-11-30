#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2021, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import re

from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
module: pdns_version
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: return the version of installed pdns
description: return the version of installed pdns

options:
  validate_version:
    description: check against the installed version.
    type: str
    required: false

"""

EXAMPLES = r"""
- name: detect pdns version
  become: true
  bodsch.dns.pdns_version:
  register: pdns_version
  check_mode: false
  ignore_errors: true

- name: detect pdns version
  become: true
  bodsch.dns.pdns_version:
    validate_version: '9.18.0'
  register: pdns_version
  check_mode: false
  ignore_errors: true
"""

RETURN = """
"""

# ---------------------------------------------------------------------------------------


class PdnsVersion(object):
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
        self.pdns_bin = module.get_bin_path("pdns_server", False)

    def run(self):
        """
        runner
        """
        result = dict(rc=127, failed=True, changed=False, full_version="unknown")

        if not self.pdns_bin:
            return dict(rc=0, failed=False, changed=False, msg="no pdns installed")

        args = []
        args.append(self.pdns_bin)
        args.append("--version")

        # self.module.log(msg=f"  args : '{args}'")

        rc, out, err = self._exec(args)

        _output = []
        _output += out.splitlines()
        _output += err.splitlines()

        msg = "unknown message"

        pattern = re.compile(
            r".*PowerDNS Authoritative Server (?P<version>(?P<major>\d+).(?P<minor>\d+).(?P<patch>\*|\d+)).*"
        )

        version = next(
            (m.groupdict() for s in _output if (m := pattern.search(s))), None
        )

        if version and isinstance(version, dict):
            version_full_string = version.get("version")
            version_major_string = version.get("major")
            version_minor_string = version.get("minor")
            version_patch_string = version.get("patch")

        if self.validate_version:
            if version_full_string == self.validate_version:
                _failed = False
                msg = f"version {self.validate_version} successful installed."
            else:
                _failed = True
                msg = f"version {self.validate_version} not installed."
        else:
            _failed = False
            msg = "pdns is installed."

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
            excutable=self.pdns_bin,
        )

        return result

    def _exec(self, commands):
        """ """
        # self.module.log(msg=f"  commands: '{commands}'")
        rc, out, err = self.module.run_command(commands, check_rc=False)

        # self.module.log(msg=f"  rc : '{rc}'")
        # if int(rc) != 0:
        #     self.module.log(msg=f"  out: '{out}'")
        #     self.module.log(msg=f"  err: '{err}'")
        #     for line in err.splitlines():
        #         self.module.log(msg=f"   {line}")

        return (rc, out, err)


# ===========================================
# Module execution.
#


def main():

    arguments = dict(validate_version=dict(required=False, type="str"))

    module = AnsibleModule(
        argument_spec=arguments,
        supports_check_mode=True,
    )

    r = PdnsVersion(module)
    result = r.run()

    # module.log(msg="= result: {}".format(result))

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
