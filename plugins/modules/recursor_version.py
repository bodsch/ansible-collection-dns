#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2021, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import re

from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
module: recursor_version
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: return the version of installed powerdns-recursor
description: return the version of installed powerdns-recursor

options:
  validate_version:
    description: check against the installed version.
    type: str
    required: false

"""

EXAMPLES = r"""
- name: detect powerdns-recursor version
  become: true
  bodsch.dns.recursor_version:
  register: recursor_version
  check_mode: false
  ignore_errors: true

- name: detect powerdns-recursor version
  become: true
  bodsch.dns.recursor_version:
    validate_version: '9.18.0'
  register: recursor_version
  check_mode: false
  ignore_errors: true
"""

RETURN = """
"""

# ---------------------------------------------------------------------------------------


class RecursorVersion(object):
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
        self.pdns_bin = module.get_bin_path("pdns_recursor", False)

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

        self.module.log(msg=f"  args : '{args}'")

        rc, out, err = self._exec(args)

        # self.module.log(msg=f"= out: {out} {type(out)}")
        # self.module.log(msg=f"= err: {err} {type(err)}")

        _out = out.splitlines()
        _err = err.splitlines()

        # self.module.log(msg=f"= _out: {_out} {type(_out)}")
        # self.module.log(msg=f"= _err: {_err} {type(_err)}")

        _output = []
        _output += _out
        _output += _err

        # if rc == 0:
        #     output = out
        # else:
        #     output = err

        # self.module.log(msg=f"= output: {_output}")
        # self.module.log(msg=f"= output: {set(_output)}")

        msg = "unknown message"

        pattern = re.compile(
            r".*PowerDNS Recursor (?P<version>(?P<major>\d+).(?P<minor>\d+).(?P<patch>\*|\d+)).*"
        )

        version = next(
            (m.groupdict() for s in _output if (m := pattern.search(s))), None
        )

        # version = next(re.search(pattern, s).group(0) for s in _output if re.search(pattern, s))
        # version = re.search(pattern, _output)
        if version:

            self.module.log(msg=f"= version: {version} {type(version)}")
            if isinstance(version, dict):
                version_full_string = version.get("version")
                version_major_string = version.get("major")
                version_minor_string = version.get("minor")
                version_patch_string = version.get("patch")
            else:
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
            msg = "powerdns-recursor is installed."

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

        self.module.log(msg=f"  rc : '{rc}'")
        if int(rc) != 0:
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")
            for line in err.splitlines():
                self.module.log(msg=f"   {line}")

        return (rc, out, err)


# ===========================================
# Module execution.
#


def main():

    module = AnsibleModule(
        argument_spec=dict(validate_version=dict(required=False, type="str")),
        supports_check_mode=True,
    )

    r = RecursorVersion(module)
    result = r.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
