#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""Reload BIND zones via rndc."""

from __future__ import absolute_import, annotations

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.dns.plugins.module_utils.bind_rndc.client import (
    RndcClient,
    RndcError,
)

DOCUMENTATION = r"""
module: bind_rndc_reload
version_added: "1.1.0"
author:
  - "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"
short_description: Reload BIND zones via rndc

description:
  - Execute C(rndc reload) to reload one or more zones.
  - If no zones specified, reloads all zones.
  - Provides idempotent zone reload with change tracking.

options:
  action:
    description:
      - C(reload) reloads zone data via C(rndc reload).
      - C(reconfig) reloads the configuration and loads newly declared zones
        via C(rndc reconfig) (required after adding/removing zone statements).
      - C(freeze) suspends updates to dynamic zones (syncs journal to file)
        so the zone file can be rewritten.
      - C(thaw) reloads frozen zones from disk and re-enables dynamic updates.
    type: str
    default: reload
    choices:
      - reload
      - reconfig
      - freeze
      - thaw

  zone_names:
    description: List of zone names to reload. Empty list reloads all zones.
    type: list
    elements: str
    default: []

  rndc_path:
    description: Path to rndc binary
    type: str
    default: /usr/sbin/rndc

  rndc_config:
    description: Path to rndc.conf configuration file
    type: str
    required: false
"""

EXAMPLES = r"""
- name: Reload all zones
  bodsch.dns.bind_rndc_reload:
    rndc_path: /usr/sbin/rndc

- name: Reload specific zones
  bodsch.dns.bind_rndc_reload:
    rndc_path: /usr/sbin/rndc
    zone_names:
      - example.com
      - example.org
"""

RETURN = r"""
changed:
  description: Whether reload was executed
  returned: always
  type: bool

stdout:
  description: rndc reload output
  returned: always
  type: str

zones_reloaded:
  description: List of zones that were reloaded
  returned: always
  type: list
"""


class BindRndcReload:
    """
    Main Class
    """

    module = None

    def __init__(self, module):
        """
        Initialize all needed Variables
        """
        self.module = module
        self.module.log("BindRndcReload::__init__()")

        self.rndc_bin = module.get_bin_path("rndc", False)

        self.action = module.params.get("action")
        self.rndc_config = module.params.get("rndc_config")
        self.zone_names = module.params.get("zone_names")

    def run(self):
        """
        Execute the module logic
        """
        self.module.log("BindRndcReload::run()")

        try:
            client = RndcClient(
                module=self.module,
                rndc_path=self.rndc_bin,
                rndc_config=self.rndc_config,
            )

            if not self.module.check_mode:
                if self.action == "reconfig":
                    result = client.reconfig()
                elif self.action == "freeze":
                    result = client.freeze(*self.zone_names)
                elif self.action == "thaw":
                    result = client.thaw(*self.zone_names)
                else:
                    result = client.reload(*self.zone_names)

                if not result["success"]:
                    self.module.fail_json(
                        msg=f"rndc {self.action} failed",
                        stdout=result["stdout"],
                        stderr=result["stderr"],
                        return_code=result["return_code"],
                    )
            else:
                result = {
                    "stdout": f"[check mode] Would {self.action} zones",
                    "success": True,
                }

            if self.action == "reconfig":
                zones_reloaded = ["reconfig"]
            else:
                zones_reloaded = self.zone_names if self.zone_names else ["all"]

            self.module.exit_json(
                changed=True,
                stdout=result["stdout"],
                zones_reloaded=zones_reloaded,
            )

        except RndcError as e:
            self.module.fail_json(msg=str(e))
        except Exception as e:
            self.module.fail_json(msg=f"Unexpected error: {str(e)}")


def main():
    """Main module execution."""

    arguments = dict(
        action=dict(
            type="str",
            default="reload",
            choices=["reload", "reconfig", "freeze", "thaw"],
        ),
        rndc_config=dict(type="str", required=False),
        zone_names=dict(type="list", elements="str", default=[]),
    )

    module: AnsibleModule = AnsibleModule(
        argument_spec=arguments,
        supports_check_mode=True,
    )

    r: BindRndcReload = BindRndcReload(module)
    result: dict[str, bool | str] | None = r.run()

    module.exit_json(**result)


if __name__ == "__main__":
    main()
