#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2023-2025, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results
from ansible_collections.bodsch.dns.plugins.module_utils.pdns.config_loader import (
    PowerDNSConfigLoader,
)
from ansible_collections.bodsch.dns.plugins.module_utils.pdns.utils import (
    generate_serial,
)
from ansible_collections.bodsch.dns.plugins.module_utils.pdns.web_api import (
    PowerDNSWebApi,
)

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
module: bind_zone_data
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: TBD
description: TBD

options:
  zone_data:
    description: []
    type: raw
    required: true
"""

EXAMPLES = r"""
"""

RETURN = """
"""

# ---------------------------------------------------------------------------------------


class PdnsZoneData(object):
    """
    Main Class
    """

    module = None

    def __init__(self, module):
        """ """
        self.module = module

        self.zone_data = module.params.get("zone_data")
        self._pdnsutil_bin = module.get_bin_path("pdnsutil", True)

    def run(self):
        """ """

        if not self._pdnsutil_bin:
            return dict(failed=False, changed=False, msg="no pdns installed.")

        cfg_invalid, pdns_cfg, msg = self.pdns_config_loader()

        if cfg_invalid:
            return dict(failed=True, msg=msg)

        config = dict(
            server_id=pdns_cfg.get("server-id", "localhost"),
            api_key=pdns_cfg.get("api_key"),
            webserver_address=pdns_cfg.get("webserver_address"),
            webserver_port=pdns_cfg.get("webserver_port"),
        )

        pdns_api = PowerDNSWebApi(module=self.module, config=config)

        result_state = []

        for d in self.zone_data:
            """ """
            res = {}

            zone = d.get("name")
            nameservers = d.get("name_servers")

            res[zone] = dict()
            zone_rrsets = {}

            zone_data = pdns_api.zone_data(zone)
            if zone_data:
                zone_rrsets = pdns_api.extract_existing_rrsets(zone_data)
            else:
                """
                keine zone vorhanden
                """
                changed = self.create_zone(pdns_api, zone, nameservers)

            zone_new_rrsets = pdns_api.build_full_rrsets(zone, d)

            rrset_changes = pdns_api.compare_rrsets(zone_rrsets, zone_new_rrsets)

            if len(rrset_changes) > 0:

                status_code, _, json_resp = pdns_api.patch_zone(zone, rrset_changes)

                if status_code in [200, 201, 204]:
                    _failed = False
                    _changed = True
                    _msg = "zone succesfully updated."
                else:
                    _failed = True
                    _changed = False
                    _msg = json_resp

                res[zone] = dict(failed=_failed, changed=_changed, msg=_msg)
            else:
                res[zone] = dict(failed=False, changed=False, msg="zone is up-to-date.")

            # self.module.log(msg="------------------------------------------------------------------")

            result_state.append(res)

        _state, _changed, _failed, state, changed, failed = results(
            self.module, result_state
        )

        result = dict(changed=_changed, failed=_failed, msg=result_state)

        return result

    def pdns_config_loader(self):
        """ """
        self.module.log(msg="PdnsZoneData::pdns_config_loader()")

        config_loader = PowerDNSConfigLoader(module=self.module)
        pdns_cfg = config_loader.load()

        config_values = {
            "api": pdns_cfg.get("api"),
            "webserver": pdns_cfg.get("webserver"),
            "api_key": pdns_cfg.get("api-key"),
            "webserver_address": pdns_cfg.get("webserver-address"),
            "webserver_port": pdns_cfg.get("webserver-port"),
        }

        # self.module.log(msg=f" config_values: '{config_values}'")

        missing_keys = [key for key, value in config_values.items() if value is None]

        if missing_keys:
            _keys = ", ".join(missing_keys)

            return (True, None, f"Missing configuration(s): {_keys}")
        else:
            return (False, config_values, "configuration are valid.")

    def create_zone(self, pdns_api, zone, nameservers):
        """ """
        self.module.log(
            msg=f"PdnsZoneData::create_zone(pdns_api={pdns_api}, zone={zone}, nameservers={nameservers})"
        )

        if isinstance(nameservers, list):
            ns = nameservers[0]
        else:
            ns = "nsX"

        serial = generate_serial()

        # wenn der DNS ein FQDN ist, muss die zone entfernt werden.

        soa = f"{ns}.{zone}. hostmaster.{zone}. {serial} 3600 1800 604800 86400"

        changed = pdns_api.zone_primary(
            zone=zone,
            soa=soa,
            nameservers=nameservers,
            ttl=640,
            comment="ansible automation",
            wantkind="native",
        )

        return changed


def main():

    arguments = dict(
        zone_data=dict(required=True, type="raw"),
    )

    module = AnsibleModule(
        argument_spec=arguments,
        supports_check_mode=True,
    )

    r = PdnsZoneData(module)
    result = r.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
