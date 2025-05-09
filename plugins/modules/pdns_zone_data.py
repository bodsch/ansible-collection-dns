#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function
import netaddr

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results
from ansible_collections.bodsch.dns.plugins.module_utils.pdns.config_loader import PowerDNSConfigLoader
from ansible_collections.bodsch.dns.plugins.module_utils.pdns.utils import generate_serial
from ansible_collections.bodsch.dns.plugins.module_utils.pdns.web_api import PowerDNSWebApi

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
module: bind_zone_data
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: TBD
description: TBD

options:
  zone_directory:
    description: []
    type: str
    required: true
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
        """
        """
        self.module = module

        self.db_type = module.params.get("type")

        if self.db_type == "sqlite3":
            self.database = module.params.get("database")

        elif self.db_type == "mysql":
            self.database = module.params.get("database")

            self.db_hostname = self.database.get("hostname", None)
            self.db_port = self.database.get("port", 3306)
            self.db_socket = self.database.get("socket", None)
            self.db_config = self.database.get("config_file", None)
            self.db_schemaname = self.database.get("schemaname", None)
            self.db_login_username = self.database.get("login", {}).get("username", None)
            self.db_login_password = self.database.get("login", {}).get("password", None)

        self.zone_data = module.params.get("zone_data")
        self._pdnsutil_bin = module.get_bin_path('pdnsutil', True)

    def run(self):
        """
        """

        if not self._pdnsutil_bin:
            return dict(
                failed=False,
                changed=False,
                msg="no pdns installed."
            )

        cfg_invalid, pdns_cfg, msg = self.pdns_config_loader()

        if cfg_invalid:
            return dict(
                failed=True,
                msg=msg
            )

        config = dict(
            server_id=pdns_cfg.get("server-id", "localhost"),
            api_key=pdns_cfg.get("api_key"),
            webserver_address=pdns_cfg.get("webserver_address"),
            webserver_port=pdns_cfg.get("webserver_port"),
        )

        pdns_api = PowerDNSWebApi(
            module=self.module,
            config=config
        )

        result_state = []

        for d in self.zone_data:
            """
            """
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
                pdns_api.patch_zone(zone, rrset_changes)

                res[zone] = dict(
                    failed=False,
                    changed=True,
                    msg="zone succesfully updated."
                )
            else:
                res[zone] = dict(
                    failed=False,
                    changed=False,
                    msg="zone is up-to-date."
                )

            # self.module.log(msg="------------------------------------------------------------------")

            result_state.append(res)

        _state, _changed, _failed, state, changed, failed = results(self.module, result_state)

        result = dict(
            changed=_changed,
            failed=_failed,
            msg=result_state
        )

        return result

    # --------------------

    def pdns_config_loader(self):
        """
        """
        config_loader = PowerDNSConfigLoader(module=self.module)
        pdns_cfg = config_loader.load()

        config_values = {
            'api': pdns_cfg.get('api'),
            'webserver': pdns_cfg.get('webserver'),
            'api_key': pdns_cfg.get('api-key'),
            'webserver_address': pdns_cfg.get('webserver-address'),
            'webserver_port': pdns_cfg.get('webserver-port')
        }

        self.module.log(msg=f" config_values: '{config_values}'")

        missing_keys = [key for key, value in config_values.items() if value is None]

        if missing_keys:
            _keys = ', '.join(missing_keys)

            return (True, None, f"Missing configuration(s): {_keys}")
        else:
            return (False, config_values, "configuration are valid.")

    def create_zone(self, pdns_api, zone, nameservers):
        """
        """
        if isinstance(nameservers, list):
            ns = nameservers[0]
        else:
            ns = "nsX"

        serial = generate_serial()
        soa = f"{ns}.{zone}. hostmaster.{zone}. {serial} 3600 1800 604800 86400"

        changed = pdns_api.zone_primary(
            zone=zone,
            soa=soa,
            nameservers=nameservers,
            ttl=640,
            comment="ansible automation",
            wantkind='native'
        )

        return changed

    def define_zone_forward_names(self):
        """
        """
        return [x.get("name") for x in self.zone_data if x.get("state", "present") and x.get("create_forward_zones", True)]

    def define_zone_reverse_names(self, ipv6=False):
        """
        """
        self.module.log(msg=f"define_zone_reverse_names(ipv6={ipv6})")

        networks = []

        def reverse_zone(network_str):
            import ipaddress
            net = ipaddress.ip_network(network_str)
            result = net.reverse_pointer + "."
            self.module.log(msg=f" = {networks}")
            return result

        if not ipv6:
            networks = [
                x.get("networks", [])
                for x in self.zone_data
                if x.get("state", "present") and x.get("create_reverse_zones", True)
            ]
        else:
            networks = [
                x.get("ipv6_networks", [])
                for x in self.zone_data
                if x.get("state", "present") and x.get("create_reverse_zones", True)
            ]

        self.module.log(msg=f" - {networks} (type(networks))")
        if networks:
            # flatten list of lists
            networks = [x for row in networks for x in row]
        else:
            networks = []

        self.module.log(msg=f" = {networks}")

        return networks

    def define_zone_networks(self):
        """
        """
        networks = [x.get("networks") for x in self.zone_data]
        # flatten list of lists
        return [x for row in networks for x in row]

    def _reverse_zone_for_network(self, network):
        """
        Erzeugt die Reverse-Zone für das angegebene Subnetz (IPv4 und IPv6).
        """
        from ansible_collections.bodsch.dns.plugins.module_utils.network_type import is_valid_ipv4

        reverse_ip = None

        if is_valid_ipv4(network):
            # Splitte die IP-Adresse und umkehre nur die ersten drei Oktette
            network_parts = network.split(".")

            # Achte darauf, dass für eine Netzadresse wie 10.11.0.0/24 nur das erste Oktett benötigt wird.
            reverse_ip = f"{network_parts[0]}.in-addr.arpa"

            result = reverse_ip

        else:
            import ipaddress

            ipv6_obj = ipaddress.IPv6Address(network)
            exploded_ip = ipv6_obj.exploded  # Gibt die vollständige IPv6-Adresse zurück

            self.module.log(msg=f"{exploded_ip}")

            # Entfernen der Doppelpunkte, Umkehren der Blöcke
            reversed_parts = list(reversed(exploded_ip.replace(":", "")))

            # Entfernen von führenden und mittleren Nullen
            # Die Ziffern, die "0" sind, müssen entfernt werden
            reversed_parts = [x for x in reversed_parts if x != '0']

            # Die Rückgabe der PTR-Adresse im richtigen Format
            reverse_ip = ".".join(reversed_parts)

            result = f"{reverse_ip}.ip6.arpa"

        if not result:
            self.module.log(msg=f"PROBLEM: {network} is neither a valid IPv4 nor a valid IPv6 network.")

        return result

    def _reverse_ip_for_host(self, ip):
        """
        Erzeugt den Reverse-DNS-Eintrag (PTR-Record) für eine gegebene Host-IP-Adresse.
        """
        reverse_ip = None

        if self.is_valid_ipv4(ip):
            reverse_ip = ".".join(ip.split('.')[::-1])
            result = f"{reverse_ip}.in-addr.arpa."

        else:
            try:
                _ipaddress = netaddr.IPAddress(ip)
                reverse_ip = _ipaddress.reverse_dns  # Diese Methode gibt uns den PTR für eine einzelne IP

                # Entfernen der "0"s in IPv6
                reverse_ip = reverse_ip.replace("0.", "")  # Entfernt führende Nullstellen
                reverse_ip = ".".join([segment for segment in reverse_ip.split(".") if segment != "0"])

                result = f"{reverse_ip}.ip6.arpa."
            except Exception as e:
                self.module.log(msg=f"ERROR: {e}")
                result = None

        if not result:
            self.module.log(msg=f"PROBLEM: {ip} is neither a valid IPv4 nor a valid IPv6 address.")

        return result

    def reverse_zone_names(self, network):
        """
        """
        self.module.log(msg=f"reverse_zone_names({network})")

        # ----------------------------------------------------
        from ansible_collections.bodsch.dns.plugins.module_utils.network_type import is_valid_ipv4

        reverse_ip = None

        if is_valid_ipv4(network):
            self.module.log(msg="ipv4")
            reverse_ip = ".".join(network.replace(network + '.', '').split('.')[::-1])
            # reverse_ip = ".".join(ip.split(".")[::-1])

            result = f"{reverse_ip}.in-addr.arpa"

        else:
            self.module.log(msg="ipv6")
            import ipaddress

            ipv6_obj = ipaddress.IPv6Address(network)
            exploded_ip = ipv6_obj.exploded  # Gibt die vollständige IPv6-Adresse zurück

            self.module.log(msg=f"{exploded_ip}")

            # Entfernen der Doppelpunkte, Umkehren der Blöcke
            reversed_parts = list(reversed(exploded_ip.replace(":", "")))

            # Entfernen von führenden und mittleren Nullen
            # Die Ziffern, die "0" sind, müssen entfernt werden
            reversed_parts = [x for x in reversed_parts if x != '0']

            # Die Rückgabe der PTR-Adresse im richtigen Format
            reverse_ip = ".".join(reversed_parts)

            result = f"{reverse_ip}.ip6.arpa"

            # return result

            # # Entfernen der Doppelpunkte, Umkehren der Blöcke und Hinzufügen von '.ip6.arpa'
            # reversed_parts = ".".join(reversed(exploded_ip.replace(":", "")))
            # return reversed_parts + ".ip6.arpa."
            #
            # try:
            #     _offset = None
            #     if network.count("/") == 1:
            #         _prefix = network.split("/")[1]
            #         _offset = int(9 + int(_prefix) // 2)
            #         # self.module.log(msg=f" - {_prefix} - {_offset}")
            #
            #     _network = netaddr.IPNetwork(str(network))
            #     _prefix = _network.prefixlen
            #     _ipaddress = netaddr.IPAddress(_network)
            #     reverse_ip = _ipaddress.reverse_dns
            #
            #     if _offset:
            #         result = reverse_ip[-_offset:]
            #
            #     if result[-1] == ".":
            #         result = result[:-1]
            #
            # except Exception as e:
            #     self.module.log(msg=f" =>  ERROR: {e}")
            #     pass

        if not result:
            self.module.log(msg=f" PROBLEM: {network} is neither a valid IPv4 nor a valid IPv6 network.")

        self.module.log(msg=f" = '{result}'")

        return result


def main():

    arguments = dict(
        zone_data=dict(
            required=True,
            type="raw"
        ),
        database=dict(
            required=False,
            type='raw'
        ),
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
if __name__ == '__main__':
    main()
