#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2021, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import re

from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: pdns_version
short_description: Return the installed PowerDNS Authoritative Server version
version_added: "0.9.0"
author:
  - Bodo Schulz (@bodsch) <bodo@boone-schulz.de>

description:
  - Executes C(pdns_server --version) on the target host and parses the version string.
  - Optionally validates the installed version against a desired version string.

options:
  validate_version:
    description:
      - If set, the module validates the installed PowerDNS version against this value.
      - The module fails when the installed version does not match.
    type: str
    required: false

notes:
  - Check mode is supported.
  - If C(pdns_server) is not installed, the module returns C(failed=false) and C(msg="no pdns installed").
"""

EXAMPLES = r"""
- name: Detect PowerDNS version
  become: true
  bodsch.dns.pdns_version:
  register: pdns_version
  check_mode: false
  ignore_errors: true

- name: Validate PowerDNS version
  become: true
  bodsch.dns.pdns_version:
    validate_version: "4.9.18"
  register: pdns_version
  check_mode: false
  ignore_errors: true

- name: Show parsed version
  ansible.builtin.debug:
    msg: "PowerDNS {{ pdns_version.full_version }} ({{ pdns_version.version.major }}.{{ pdns_version.version.minor }}.{{ pdns_version.version.patch }})"
"""

RETURN = r"""
failed:
  description:
    - Indicates whether the module considers the result a failure.
    - With C(validate_version) set, C(true) if the installed version does not match.
  returned: always
  type: bool

changed:
  description:
    - Always C(false); the module is read-only.
  returned: always
  type: bool

rc:
  description:
    - Return code used by the module implementation.
  returned: always
  type: int
  sample: 0

msg:
  description:
    - Human readable status message.
  returned: always
  type: str
  sample:
    - "pdns is installed."
    - "no pdns installed"
    - "version 4.9.18 successful installed."
    - "version 4.9.18 not installed."

full_version:
  description:
    - Parsed version string as reported by C(pdns_server --version).
  returned: when pdns_server is installed
  type: str
  sample: "4.9.18"

version:
  description:
    - Parsed version components.
  returned: when pdns_server is installed
  type: dict
  contains:
    major:
      description: Major version.
      type: int
      returned: always
    minor:
      description: Minor version.
      type: int
      returned: always
    patch:
      description: Patch version.
      type: int
      returned: always

excutable:
  description:
    - Absolute path to the C(pdns_server) executable discovered on the target.
  returned: always
  type: str
  sample: "/usr/sbin/pdns_server"
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
