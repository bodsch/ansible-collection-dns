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
        self.pdns_bin = module.get_bin_path('pdns_server', False)

    def run(self):
        """
          runner
        """
        result = dict(
            rc=127,
            failed=True,
            changed=False,
            full_version="unknown"
        )

        if not self.pdns_bin:
            return dict(
                rc=0,
                failed=False,
                changed=False,
                msg="no pdns installed"
            )

        args = []
        args.append(self.pdns_bin)
        args.append('--version')

        self.module.log(msg=f"  args : '{args}'")

        rc, out, err = self._exec(args)

        #self.module.log(msg=f"= result: {result}")

        if rc == 0:
            output = out
        else:
            output = err

        msg = "unknown message"

        # pdns_server --version
        # Apr 25 01:21:25 PowerDNS Authoritative Server 4.9.4 (C) PowerDNS.COM BV
        # Apr 25 01:21:25 Using 64-bits mode. Built using gcc 14.2.1 20250128.
        # Apr 25 01:21:25 PowerDNS comes with ABSOLUTELY NO WARRANTY. This is free software, and you are welcome to redistribute it according to the terms of the GPL version 2.
        # Apr 25 01:21:25 Features: libcrypto-ecdsa libcrypto-ed25519 libcrypto-ed448 libcrypto-eddsa libgeoip libmaxminddb lua lua-records protobuf sodium curl DoT scrypt
        # Apr 25 01:21:25 Built-in modules:
        # Apr 25 01:21:25 Loading '/usr/lib/powerdns/libbindbackend.so'
        # Apr 25 01:21:25 Loading '/usr/lib/powerdns/libgeoipbackend.so'
        # Apr 25 01:21:25 Unable to load module '/usr/lib/powerdns/libgeoipbackend.so': libyaml-cpp.so.0.8: cannot open shared object file: No such file or directory
        # Apr 25 01:21:25 DNSBackend unable to load module in libgeoipbackend.so
        pattern = re.compile(
            r".*PowerDNS Authoritative Server (?P<version>(?P<major>\d+).(?P<minor>\d+).(?P<patch>\*|\d+)).*")
        version = re.search(pattern, output)
        if version:
            version_full_string = version.group('version')
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
            msg = "pdns is installed."

        result = dict(
            failed=_failed,
            rc=0,
            msg=msg,
            full_version=version_full_string,
            version=dict(
                major=int(version_major_string),
                minor=int(version_minor_string),
                patch=int(version_patch_string)
            ),
            excutable=self.pdns_bin
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
        argument_spec=dict(
            validate_version=dict(
                required=False,
                type="str"
            )
        ),
        supports_check_mode=True,
    )

    r = PdnsVersion(module)
    result = r.run()

    module.log(msg="= result: {}".format(result))

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
