#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""Query BIND status via rndc."""

from __future__ import absolute_import, annotations

from typing import Any, Never

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.dns.plugins.module_utils.bind_rndc.client import (
    RndcClient,
    RndcError,
)
from ansible_collections.bodsch.dns.plugins.module_utils.bind_rndc.parser import (
    RndcOutputParser,
)

DOCUMENTATION = r"""
module: bind_rndc_status
version_added: "1.1.0"
author:
  - "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"
short_description: Query BIND status via rndc

description:
  - Execute C(rndc status) to check BIND server and zone status.
  - Useful for pre-flight checks before zone updates.

options:

  rndc_config:
    description: Path to rndc.conf configuration file
    type: str
    required: false

  zone:
    description: Optional zone name to check specific zone status
    type: str
    required: false
"""

EXAMPLES = r"""
- name: Check overall BIND status
  bodsch.dns.bind_rndc_status:

- name: Check status of specific zone
  bodsch.dns.bind_rndc_status:
    zone: example.com
"""

RETURN = r"""
status:
  description: Parsed status information
  returned: always
  type: dict
  sample:
    version: "BIND 9.16.x"
    hostname: "ns1.example.com"
    zones_loaded: 5

stdout:
  description: Raw rndc status output
  returned: always
  type: str

success:
  description: Whether rndc status command succeeded
  returned: always
  type: bool
"""


class BindRndcStatus:
    """
    Main Class
    """

    def __init__(self, module) -> None:
        """
        Initialize all needed Variables
        """
        self.module = module
        self.module.log("BindRndcStatus::__init__()")

        # self.validate_version = module.params.get("validate_version")
        self.rndc_bin: str = module.get_bin_path("rndc", False)

        self.rndc_config: str | None = module.params.get("rndc_config")
        self.zone: str | None = module.params.get("zone")

    def run(self) -> dict[str, bool | str] | None:
        """
        runner
        """
        self.module.log("BindRndcStatus::run()")

        if not self.rndc_bin:
            return dict[str, bool | str](
                failed=True, changed=False, msg="no rndc installed."
            )

        try:
            client: RndcClient = RndcClient(
                module=self.module,
                rndc_path=self.rndc_bin,
                rndc_config=self.rndc_config,
            )
            client_status: Any | dict[str, bool | str] = client.status(zone=self.zone)

            if not client_status["success"]:
                self.module.fail_json(
                    msg="rndc status failed",
                    stdout=client_status["stdout"],
                    stderr=client_status["stderr"],
                    return_code=client_status["return_code"],
                )

            parser = RndcOutputParser()
            parsed = parser.parse_status(client_status["stdout"])

            return dict[str, bool | str](
                changed=False,
                status=parsed,
                stdout=client_status["stdout"],
                success=True,
            )

        except RndcError as e:
            self.module.fail_json(msg=str(e))
        except Exception as e:
            self.module.fail_json(msg=f"Unexpected error: {str(e)}")


def main() -> Never:
    """Main module execution."""

    arguments: dict[str, dict[str, str | bool]] = dict[str, dict[str, str | bool]](
        rndc_config=dict[str, str | bool](type="str", required=False),
        zone=dict[str, str | bool](type="str", required=False),
    )

    module: AnsibleModule = AnsibleModule(
        argument_spec=arguments,
        supports_check_mode=True,
    )

    r: BindRndcStatus = BindRndcStatus(module)
    result: dict[str, bool | str] | None = r.run()

    module.exit_json(**result)


if __name__ == "__main__":
    main()
