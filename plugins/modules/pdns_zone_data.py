#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function
import os
import re
import netaddr

from ansible.module_utils.basic import AnsibleModule
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

        config_loader = PowerDNSConfigLoader(module=self.module)
        cfg = config_loader.load()

        config_values = {
            'api': cfg.get('api'),
            'webserver': cfg.get('webserver'),
            'api-key': cfg.get('api-key'),
            'webserver-address': cfg.get('webserver-address'),
            'webserver-port': cfg.get('webserver-port')
        }

        missing_keys = [key for key, value in config_values.items() if value is None]

        if missing_keys:
            _keys = ', '.join(missing_keys)
            return dict(
                failed=True,
                msg=f"Missing configuration(s): {_keys}"
            )

        pdns_api = PowerDNSWebApi(
            module=self.module,
            server_id=config_values.get("server_id"),
            api_key=config_values.get("api_key"),
            webserver_address=config_values.get("webserver_address")
        )

        if isinstance(self.zone_data, list):
            """
            """
            changed = True

            for d in self.zone_data:
                domain_type = d.get("type")
                zone = d.get("name")
                nameservers = d.get("name_servers")
                networks = d.get("networks", None)
                hosts = d.get("hosts")
                mail_servers = d.get("mail_servers", None)
                services = d.get("services", None)
                text = d.get("text", None)

                # list of all zones ...
                # pdns_api.zone_list()

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

                # PTR ?

            zone_list = pdns_api.zone_list(zone=zone)

            pdns_api.add_records(zone=zone, record_type="A", records=hosts)

            # if networks:
            #       # PTR ?
            #     reverse_zones = self.define_zone_reverse_names()
            #     reverse_zones += self.define_zone_reverse_names(ipv6=True)
            #
            #     #reverse_data = self.reverse_zone_data(reverse_zones)
            #
            #     self.module.log(msg=f" reverse_zones: '{reverse_zones}'")
            #
            #     reverse_networks = []
            #     for x in reverse_zones:
            #         reverse_networks.append(self._reverse_zone_for_network(x))
            #     self.module.log(msg=f" = '{reverse_networks}'")
            #
            #     #self.module.log(msg=f" reverse_data : '{reverse_data}'")
            #
            #     pdns_api.add_records(zone=zone, record_type="PTR", records=reverse_networks)

            if mail_servers:
                pdns_api.add_records(zone=zone, record_type="MX", records=mail_servers)
            if services:
                pdns_api.add_records(zone=zone, record_type="SRV", records=services)
            if text:
                pdns_api.add_records(zone=zone, record_type="TXT", records=text)

        result = dict(
            failed=True
        )

        return result

    # def generate_serial(self, base_serial=None):
    #     """
    #     """
    #
    #     today = datetime.datetime.utcnow().strftime("%Y%m%d")
    #     counter = 1
    #     serial = int(f"{today}{counter:02d}")
    #
    #     # Optional: existing serial auslesen und erhöhen
    #     if base_serial and str(base_serial).startswith(today):
    #         old_counter = int(str(base_serial)[-2:])
    #         counter = old_counter + 1
    #         serial = int(f"{today}{counter:02d}")
    #
    #     return serial

    # --------------------

    def create_soa(self, domain, nameservers):
        """
            pdnsutil add-record acme-inc.com @ SOA "ns1.acme-inc.com. hostmaster.acme-inc.com. 2025050801 3600 1800 604800 86400"
        """
        self.module.log(msg=f"create_soa({domain}, {nameservers})")

        if isinstance(nameservers, list):
            ns = nameservers[0]
        else:
            ns = "nsX"

        args = []
        args.append(self._pdnsutil_bin)
        args.append("add-record")
        args.append(domain)
        args.append("@")
        args.append("SOA")
        args.append(f"{ns}.{domain}.")
        args.append(f"hostmaster.{domain}.")
        args.append(self.generate_serial())

    def create_zone(self, domain, nameservers, hosts):
        """
        """

        args = []
        args.append(self._pdnsutil_bin)
        args.append("create-zone")
        args.append(domain)

        self.module.log(msg=f"  args : '{args}'")

        rc, out, err = self._exec(args)

        _output = []
        _output += out.splitlines()
        _output += err.splitlines()

        self.module.log(msg=f"  output : '{_output}'")

        escaped_domain = re.escape(domain)

        pattern_domain_created = re.compile(rf"Creating empty zone '(?P<domain>{escaped_domain})'")

        _result_domain_created = next((m.groupdict() for s in _output if (m := pattern_domain_created.search(s))), None)

        if _result_domain_created:
            """
            """
            self.create_soa(domain, nameservers)

    def verify_zone(self, domain):
        """
        """

        args = []
        args.append(self._pdnsutil_bin)
        args.append("check-zone")
        args.append(domain)

        self.module.log(msg=f"  args : '{args}'")

        rc, out, err = self._exec(args)

    def list_zone(self, domain):
        """
        """

        args = []
        args.append(self._pdnsutil_bin)
        args.append("list-zone")
        args.append(domain)

        self.module.log(msg=f"  args : '{args}'")

        rc, out, err = self._exec(args)

        _output = []
        _output += out.splitlines()
        _output += err.splitlines()

        self.module.log(msg=f"  output : '{_output}'")

        escaped_domain = re.escape(domain)

        pattern_domain_notfound = re.compile(rf"Zone '(?P<domain>{escaped_domain})' not found!")
        pattern_domain_exists = re.compile(rf"Zone '(?P<domain>{escaped_domain})' exists already")
        pattern_domain_soa = re.compile(rf"^(?P<domain>{escaped_domain})\t.*\tSOA\t")

        # self.module.log(msg=f"  - '{pattern_domain_soa}'")

        _result_domain_notfound = next((m.groupdict() for s in _output if (m := pattern_domain_notfound.search(s))), None)
        _result_domain_exists = next((m.groupdict() for s in _output if (m := pattern_domain_exists.search(s))), None)
        _result_domain_soa = next((m.groupdict() for s in _output if (m := pattern_domain_soa.search(s))), None)

        if _result_domain_notfound:
            # and isinstance(version, dict):
            # self.module.log(msg=f"  = : '{_result_domain_notfound}'")
            return (0, False, err.strip())

        if _result_domain_exists:
            # and isinstance(version, dict):
            self.module.log(msg=f"  = : '{_result_domain_exists}'")

        if _result_domain_soa:
            # and isinstance(version, dict):
            # self.module.log(msg=f"  = : '{_result_domain_soa}'")
            return (0, True, f"Domain {domain} already created.")

        result = dict(
            rc=rc,
            msg=msg
        )

        self.module.log(msg=f"  result : '{result}'")

        return result

    def forward_zone_data(self, forward_zones):
        """
        """
        self.module.log(msg=f"forward_zone_data({forward_zones})")
        result = []
        for name in forward_zones:
            self.module.log(msg=f" - '{name}'")

            res = {}
            res[name] = {}

            hash, serial = self.read_zone_file(name)

            res[name] = dict(
                filename=str(name),
                sha256=str(hash),
                serial=str(serial)
            )

            result.append(res)

        self.module.log(msg=f" = '{result}'")

        return result

    def reverse_zone_data(self, reverse_zones):
        """
        """
        self.module.log(msg=f"reverse_zone_data({reverse_zones})")

        result = []
        for name in reverse_zones:
            self.module.log(msg=f" - '{name}'")

            # filename = self.reverse_zone_names(name)
            #
            # res = {}
            # res[name] = {}
            #
            # hash, serial = self.read_zone_file(filename)
            #
            # res[name] = dict(
            #     filename=str(filename),
            #     sha256=str(hash),
            #     serial=str(serial),
            #     network=str(name)
            # )

            result.append(res)

        self.module.log(msg=f" = '{result}'")

        return result

    def read_zone_file(self, zone_file):
        """
        """
        # self.module.log(msg=f"read_zone_file({zone_file})")
        # line = None
        hash = None
        serial = None
        _file_name = os.path.join(self.zone_directory, zone_file)

        # self.module.log(msg=f"   zone_directory: '{self.zone_directory}'")
        # self.module.log(msg=f"   zone_file     : '{zone_file}'")
        # self.module.log(msg=f"   file_name     : '{_file_name}'")
        # self.module.log(msg=f"                 : '{os.path.join(self.zone_directory, _file_name)}'")

        if os.path.exists(_file_name):
            with open(_file_name, "r") as f:
                # zone_data = f.readlines()
                # read first 4 lines from file
                zone_data = [next(f) for _ in range(5)]
                # self.module.log(msg=f"                 : {zone_data}")
                pattern = re.compile(
                    r'; Hash:.*(?P<hash>[0-9A-Za-z]{64}) (?P<timestamp>[0-9]+)', re.MULTILINE)

                # find regex in list
                # [0]  # Read Note
                _list = list(filter(pattern.match, zone_data))

                if isinstance(_list, list) and len(_list) > 0:
                    line = _list[0].strip()
                    if len(line) > 0:
                        arr = line.split(" ")
                        hash = arr[2]
                        serial = arr[3]

        self.module.log(msg=f"= hash: {hash}, serial: {serial}")

        return (hash, serial)

    def _exec(self, args, check_rc=False):
        """
        """
        rc, out, err = self.module.run_command(args, check_rc=check_rc)

        self.module.log(msg=f"  rc : '{rc}'")

        self.module.log(msg=f"  out: '{out}'")
        self.module.log(msg=f"  err: '{err}'")
        for line in err.splitlines():
            self.module.log(msg=f"   {line}")

        return rc, out, err

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
        # type=dict(
        #     default="sqlite3",
        #     choices=[
        #         "sqlite3",
        #         "mariadb"
        #     ]
        # ),
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
