#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, division, print_function

import hashlib
import os
import re
import time

from ansible.module_utils.basic import AnsibleModule

__metaclass__ = type

ANSIBLE_METADATA = {
    "metadata_version": "0.1",
    "status": ["preview"],
    "supported_by": "community",
}

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
module: kdig
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: TBD
description: TBD

options:
  root_dns:
    description: []
    required: false
    default: k.root-servers.net
    type: str
  key_signing_key:
    description: []
    required: false
    default: 257
    type: int
  trust_keyfile:
    description: []
    required: false
    default: /etc/trusted-key.key
    type: str
  parameters:
    description: []
    required: false
    type: list

"""

EXAMPLES = r"""
"""

RETURN = """
"""

# ---------------------------------------------------------------------------------------


class Kdig(object):
    """
    Main Class to implement the Icinga2 API Client
    """

    module = None

    def __init__(self, module):
        """
        Initialize all needed Variables
        """
        self.module = module

        self._kdig_bin = module.get_bin_path("kdig", True)

        self.root_dns = module.params.get("root_dns")
        self.key_signing_key = module.params.get("key_signing_key")
        self.trust_keyfile = module.params.get("trust_keyfile")
        self.parameters = module.params.get("parameters")

        self.trust_keyfile_checksum = "/etc/.trusted-key.key.checksum"

    def run(self):
        """
        run
        """
        result = dict(failed=True, ansible_module_results="failed")

        _checksum = ""
        _old_checksum = ""

        if not self._kdig_bin:
            return dict(rc=1, failed=True, msg="no installed kdig found")

        if os.path.isfile(self.trust_keyfile_checksum):
            with open(self.trust_keyfile_checksum, "r") as fp:
                _old_checksum = fp.readlines()[0]

        args = []
        args.append(self._kdig_bin)
        args.append("DNSKEY")
        args.append(".")
        args.append(f"@{self.root_dns}")
        args.append("+noall")
        args.append("+answer")

        self.module.log(msg=f" - args {args}")

        rc, out, err = self._exec(args)

        if rc == 0:
            pattern = re.compile(
                r"(?P<key>.*DNSKEY\s+{}.*)".format(self.key_signing_key), re.MULTILINE
            )

            result = re.search(pattern, out)

            dnskey = result.group("key")

            _checksum = self.__checksum(dnskey)

            if _old_checksum != _checksum:
                """
                rename old trust file
                """
                if os.path.isfile(self.trust_keyfile):
                    date_string = time.strftime("%Y%m%d%H%M%S")
                    _trust_keyfile_backup = f"{self.trust_keyfile}_{date_string}"

                    os.rename(self.trust_keyfile, _trust_keyfile_backup)

                with open(self.trust_keyfile, "w") as trust_keyfile:
                    trust_keyfile.write(dnskey)

                """
                  persist checksum
                """
                with open(self.trust_keyfile_checksum, "w") as checksum_file:
                    checksum_file.write(_checksum)

                result = dict(
                    failed=False,
                    changed=True,
                    msg=f"{self.trust_keyfile} successfully updated",
                )
            else:
                result = dict(
                    failed=False,
                    changed=False,
                    msg=f"{self.trust_keyfile} is up-to-date",
                )

        return result

    def _exec(self, args):
        """ """
        rc, out, err = self.module.run_command(args, check_rc=True)
        # self.module.log(msg=f"  rc : '{rc}'")
        # self.module.log(msg=f"  out: '{out}' ({type(out)})")
        # self.module.log(msg=f"  err: '{err}'")
        return rc, out, err

    def __checksum(self, plaintext):
        """
        create checksum from string
        """
        _bytes = plaintext.encode("utf-8")
        _hash = hashlib.sha256(_bytes)
        checksum = _hash.hexdigest()

        return checksum


# ---------------------------------------------------------------------------------------
# Module execution.
#


def main():
    """ """
    module = AnsibleModule(
        argument_spec=dict(
            root_dns=dict(required=False, default="k.root-servers.net", type="str"),
            key_signing_key=dict(required=False, default=257, type="int"),
            trust_keyfile=dict(
                required=False, default="/etc/trusted-key.key", type="str"
            ),
            parameters=dict(required=False, type="list"),
        ),
        supports_check_mode=True,
    )

    c = Kdig(module)
    result = c.run()

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
