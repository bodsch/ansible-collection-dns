#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""DDNS record updates via nsupdate."""

from __future__ import absolute_import, annotations

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.dns.plugins.module_utils.bind_ddns.nsupdate import (
    NsupdateClient,
    NsupdateError,
    NsupdateExecutionError,
)

DOCUMENTATION = r"""
module: bind_nsupdate
version_added: "1.1.0"
author:
  - "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"
short_description: DDNS record updates via nsupdate

description:
  - Execute DDNS updates using the C(nsupdate) utility.
  - Supports both authenticated (TSIG) and unauthenticated updates.
  - Allows adding, updating, or deleting DNS records without modifying zone files.

options:
  zone:
    description: Zone name
    type: str
    required: true

  updates:
    description: List of nsupdate commands to execute (without 'send')
    type: list
    elements: str
    required: true
    example:
      - "update add www.example.com. 300 A 192.0.2.10"
      - "update delete mail.example.com. A"

  key_name:
    description: TSIG key name for authenticated updates
    type: str
    required: false

  key_secret:
    description: TSIG key secret for authenticated updates
    type: str
    required: false
    no_log: true

  key_algorithm:
    description: TSIG key algorithm
    type: str
    default: HMAC-SHA256
    choices:
      - HMAC-MD5
      - HMAC-SHA1
      - HMAC-SHA256
      - HMAC-SHA512

  server:
    description:
      - Target server the update is sent to.
      - If unset, C(nsupdate) resolves the zone's primary master from its SOA
        record, which for public zone names can target the wrong server.
    type: str
    required: false

  port:
    description: Target server port
    type: int
    default: 53
"""

EXAMPLES = r"""
- name: Add A record via DDNS
  bodsch.dns.bind_nsupdate:
    zone: example.com
    updates:
      - "update add web.example.com. 300 A 192.0.2.100"

- name: Update multiple records with TSIG authentication
  bodsch.dns.bind_nsupdate:
    zone: example.com
    updates:
      - "update add srv1.example.com. 300 A 192.0.2.50"
      - "update add srv2.example.com. 300 A 192.0.2.51"
    key_name: ddns-key
    key_secret: "your-tsig-secret"
    key_algorithm: HMAC-SHA256

- name: Delete A record
  bodsch.dns.bind_nsupdate:
    zone: example.com
    updates:
      - "update delete old.example.com. A"
"""

RETURN = r"""
changed:
  description: Whether the update was performed
  returned: always
  type: bool

stdout:
  description: nsupdate output
  returned: always
  type: str

success:
  description: Whether the nsupdate command succeeded
  returned: always
  type: bool

commands_executed:
  description: List of commands sent to nsupdate
  returned: always
  type: list
"""


class BindNSUpdate:
    """
    Main Class
    """

    def __init__(self, module):
        """
        Initialize all needed Variables
        """
        self.module = module
        self.module.log("BindNSUpdate::__init__()")

        # self.validate_version = module.params.get("validate_version")
        self.nsupdate_bin = module.get_bin_path("nsupdate", False)

        self.zone = module.params.get("zone")
        self.updates = module.params.get("updates")
        self.key_name = module.params.get("key_name")
        self.key_secret = module.params.get("key_secret")
        self.key_algorithm = module.params.get("key_algorithm")
        self.server = module.params.get("server")
        self.port = module.params.get("port")
        # self.nsupdate_path = module.params.get("nsupdate_path")

    def run(self):
        """
        runner
        """
        self.module.log("BindNSUpdate::run()")

        result = dict(failed=True, changed=False, msg="Initialize.")

        if not self.nsupdate_bin:
            return dict(failed=True, changed=False, msg="no nsupdate installed.")

        try:
            client = NsupdateClient(
                module=self.module,
                nsupdate_path=self.nsupdate_bin,
                key_name=self.key_name,
                key_secret=self.key_secret,
                key_algorithm=self.key_algorithm,
                server=self.server,
                port=self.port,
            )

            if self.module.check_mode:
                self.module.exit_json(
                    changed=True,
                    stdout="[check mode] Would execute nsupdate commands",
                    success=True,
                    commands_executed=self.updates,
                )

            result = client.execute(self.zone, self.updates)

            if not result["success"]:
                self.module.fail_json(
                    msg="nsupdate failed",
                    stdout=result["stdout"],
                    stderr=result["stderr"],
                    return_code=result["return_code"],
                    commands_executed=self.updates,
                )

            self.module.exit_json(
                changed=result.get("changed", True),
                stdout=result["stdout"],
                success=True,
                commands_executed=self.updates,
            )

        except NsupdateExecutionError as e:
            detail = (e.stderr or e.stdout or "").strip()
            self.module.fail_json(
                msg=f"nsupdate failed: {detail}" if detail else "nsupdate failed",
                stdout=e.stdout,
                stderr=e.stderr,
                return_code=e.return_code,
                commands_executed=self.updates,
            )
        except NsupdateError as e:
            self.module.fail_json(msg=str(e))
        except Exception as e:
            self.module.fail_json(msg=f"Unexpected error: {str(e)}")


def main():
    """Main module execution."""

    arguments = dict(
        zone=dict(type="str", required=True),
        updates=dict(type="list", elements="str", required=True),
        key_name=dict(type="str", required=False),
        key_secret=dict(type="str", required=False, no_log=True),
        key_algorithm=dict(
            type="str",
            default="HMAC-SHA256",
            choices=["HMAC-MD5", "HMAC-SHA1", "HMAC-SHA256", "HMAC-SHA512"],
        ),
        server=dict(type="str", required=False),
        port=dict(type="int", default=53),
    )

    module = AnsibleModule(
        argument_spec=arguments,
        supports_check_mode=True,
    )

    r = BindNSUpdate(module)
    result = r.run()

    module.exit_json(**result)


if __name__ == "__main__":
    main()
