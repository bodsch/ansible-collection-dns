# python 3 headers, required if submitting to Ansible
from __future__ import absolute_import, division, print_function

__metaclass__ = type

# import netaddr
import hashlib
import json
import time
from typing import Hashable, TypeVar

from ansible.utils.display import Display
from ansible_collections.bodsch.dns.plugins.module_utils.network_type import reverse_dns

T = TypeVar("T", bound=Hashable)

display = Display()

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
name: bind
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

description: TBD
short_description: TBD
"""

EXAMPLES = """
"""

RETURN = """
"""

# ---------------------------------------------------------------------------------------


class FilterModule(object):
    """ """

    def filters(self):
        return {
            "zone_type": self.zone_type,
            "zone_serial": self.zone_serial,
            "forward_zone_data": self.forward_zone_data,
            "reverse_zone_data": self.reverse_zone_data,
            "zone_filename": self.zone_filename,
            # "combine_zone_data": self.combine_zone_data,
            # "when_reverse_zone": self.when_reverse_zone,
        }

    def zone_type(self, data, all_addresses):
        """ """
        # display.v(f"zone_type({data}, {all_addresses})")
        result = None
        _type = data.get("type", None)
        _primaries = data.get("primaries", None)
        _forwarders = data.get("forwarders", None)

        # display.v(f"  - type       : {_type}")
        # display.v(f"  - primaries  : {_primaries}")
        # display.v(f"  - forwarders : {_forwarders}")

        if _type and _type in ["primary", "secondary", "forward"]:
            # display.v(f"    type is defined and {_type}")
            result = _type
            # display.v(f"  1 = {result}")

        elif not _type and _primaries:
            # display.v("    not _type and _primaries")
            # display.v(f"      - all_addresses : {all_addresses}")
            # display.v(f"      - primaries     : {_primaries}")

            primaries_in_all_addresses = [x for x in all_addresses if x in _primaries]
            # display.v(f"      - primaries_in_all_addresses : {primaries_in_all_addresses}")

            primaries_in_all_addresses = len(primaries_in_all_addresses) > 0
            # display.v(f"        {primaries_in_all_addresses}")

            if primaries_in_all_addresses:
                result = "primary"
            else:
                result = "secondary"
            # display.v(f"  2 = {result}")

        elif not _type and _forwarders:
            # display.v(f"    not _type and _forwarders")
            result = "forward"
            # display.v(f"  3 = {result}")

        # display.v(f"  = {result}")

        return result

    def zone_serial(self, data, zone_hash, exists_hashes, network=None):
        """
        define serial for zone data or take existing serial when hash are equal

        input:
            data:
                - 'acme-inc.local'
            zone_hash:
                - '79803e1202406f3051d3b151ed953db2a98c86f61d5c9eead61671377d10320d'
            exists_hashes:
                - '{
                      'zone_data': {
                        'forward': [{
                          'example.com': {
                            'filename': 'example.com',
                            'hash': '; Hash: 8d591afa6aa30ca0ea7b0293a2468b57b81f591681cd932a7e7a42de5a2a0004 1702835325',
                            'sha256': '8d591afa6aa30ca0ea7b0293a2468b57b81f591681cd932a7e7a42de5a2a0004',
                            'serial': '1702835325'
                           }
                        }, {
                          'acme-inc.local': {
                            'filename': 'acme-inc.local',
                            'hash': '; Hash: 79803e1202406f3051d3b151ed953db2a98c86f61d5c9eead61671377d10320d 1702835326',
                            'sha256': '79803e1202406f3051d3b151ed953db2a98c86f61d5c9eead61671377d10320d',
                            'serial': '1702835326'
                           }
                        }],
                        'reverse': [{
                          '192.0.2': {
                            'filename': '2.0.192.in-addr.arpa',
                            'hash': None,
                            'sha256': 'None',
                            'serial': 'None',
                            'network': '192.0.2'
                          }
                        }],
                      },
                   }'
            network:
                - None or
                - 'acme-inc.local'
        """
        display.v(
            f"bodsch.dns.zone_serial(data: {data}, zone_hash: {zone_hash}, exists_hashes: {exists_hashes}, network: {network})"
        )

        result = dict(hash=zone_hash, serial=int(time.time()))
        domain_data = None

        if isinstance(exists_hashes, str):
            exists_hashes = json.loads(exists_hashes)

        zone_data = exists_hashes.get("zone_data", [])

        if network:
            hashes = zone_data.get("reverse", {})
            domain_data = [x for x in hashes for k, v in x.items() if k == network]
        else:
            hashes = zone_data.get("forward", {})
            domain_data = [x for x in hashes for k, v in x.items() if k == data]

        if isinstance(domain_data, list) and len(domain_data) > 0:
            domain_data = domain_data[0]

            if network:
                domain_data = domain_data.get(network)
            else:
                domain_data = domain_data.get(data)

        if domain_data and len(domain_data) > 0:
            _serial = domain_data.get("serial", "")

            if _serial and _serial != "None":
                result.update({"serial": _serial})

        display.v(f"  = {result}")
        return result

    def forward_zone_data(self, data, soa, ansible_hostname):
        """ """
        # display.v(f"forward_zone_data({data}, {soa}, {ansible_hostname})")

        domain = data.get("name")
        hostmaster_email = data.get("hostmaster_email", None)
        soa_ns_server = data.get("name_servers", [])
        other_name_servers = data.get("other_name_servers", None)
        mail_servers = data.get("mail_servers", [])

        if not hostmaster_email:
            hostmaster_email = f"hostmaster.{domain}."
        else:
            if not hostmaster_email[:-1] == ".":
                hostmaster_email = f"{hostmaster_email}.{domain}."

        # append domain to ns entry, when the tast char not a dot is
        for x in range(len(soa_ns_server)):
            # display.v(f"   - {soa_ns_server[x]}")
            if not soa_ns_server[x][-1:] == ".":
                soa_ns_server[x] = f"{soa_ns_server[x]}.{domain}."

        if len(soa_ns_server) == 0:
            soa_ns_server.append(f"{ansible_hostname}.{domain}.")

        if other_name_servers:
            # display.v(f" - {other_name_servers}")
            other_name_servers = self.__append(other_name_servers)

        if not mail_servers[-1:] == ".":
            self.__append(mail_servers, domain)

        result = dict(
            ttl=soa.get("ttl"),
            domain=domain,
            soa_name_server=soa_ns_server,
            other_name_servers=other_name_servers,
            mail=mail_servers,
            hostmaster_email=hostmaster_email,
            refresh=soa.get("time_to_refresh"),
            retry=soa.get("time_to_retry"),
            expire=soa.get("time_to_expire"),
            minimum=soa.get("minimum_ttl"),
            hosts=data.get("hosts", []),
            delegate=data.get("delegate", []),
            services=data.get("services", []),
            text=data.get("text", []),
            caa=data.get("caa", []),
            naptr=data.get("naptr", []),
        )

        result_hash = self.__hash(result)

        return dict(forward_zone_data=result, zone_hash=result_hash)

    def reverse_zone_data(self, data, soa, ansible_hostname):
        """
        input:
            data: [
            {
              'name': 'molecule.lan', 'primaries': ['172.17.0.2'], 'name_servers': ['ns1.acme-inc.local.', 'ns2.acme-inc.local.'],
              'hostmaster_email': 'admin',
              'hosts': [
                {'name': 'srv001', 'ip': '172.17.2.1', 'aliases': ['www']},
                {'name': 'srv002', 'ip': '172.17.2.2'}
              ]
            },
            '172.17'
        ],
            soa: {'ttl': '1W', 'time_to_refresh': '1D', 'time_to_retry': '1H', 'time_to_expire': '1W', 'minimum_ttl': '1D'},
            ansible_hostname: instance

        """
        display.v(
            f"bodsch.dns.reverse_zone_data(data: {data}, soa: {soa}, ansible_hostname: {ansible_hostname})"
        )

        revip = None

        if isinstance(data, list) and len(data) == 2:
            revip = data[1]
            data = data[0]

        result = dict()

        domain = data.get("name")
        hostmaster_email = data.get("hostmaster_email", None)
        soa_ns_server = data.get("name_servers", [])
        other_name_servers = data.get("other_name_servers", None)

        display.v(f"  - domain            : {domain}")
        display.v(f"  - hostmaster_email  : {hostmaster_email}")
        display.v(f"  - soa_ns_server     : {soa_ns_server}")
        display.v(f"  - other_name_servers: {other_name_servers}")

        display.v("------------------------------")

        if not hostmaster_email:
            hostmaster_email = f"hostmaster.{domain}."
        else:
            if not hostmaster_email[:-1] == ".":
                hostmaster_email = f"{hostmaster_email}.{domain}."

        # append domain to ns entry, when the tast char not a dot is
        for x in range(len(soa_ns_server)):
            # display.v(f"   - {soa_ns_server[x]}")
            if not soa_ns_server[x][-1:] == ".":
                soa_ns_server[x] = f"{soa_ns_server[x]}.{domain}."

        if len(soa_ns_server) == 0:
            soa_ns_server.append(f"{ansible_hostname}.{domain}.")

        if other_name_servers:
            # display.v(f" - {other_name_servers}")
            other_name_servers = self.__append(other_name_servers)

        display.v("------------------------------")
        display.v(f"  - revip             : {revip}")
        reverse_ip = reverse_dns(revip)
        display.v(f"  - reverse_ip        : {reverse_ip}")
        display.v("------------------------------")

        result = dict(
            ttl=soa.get("ttl"),
            domain=domain,
            soa_name_server=soa_ns_server,
            other_name_servers=other_name_servers,
            hostmaster_email=hostmaster_email,
            refresh=soa.get("time_to_refresh"),
            retry=soa.get("time_to_retry"),
            expire=soa.get("time_to_expire"),
            minimum=soa.get("minimum_ttl"),
            hosts=data.get("hosts", []),
            revip=reverse_ip,
        )

        result_hash = self.__hash(result)

        display.v(f"  = {result} - {result_hash}")

        return dict(reverse_zone_data=result, zone_hash=result_hash)

    def zone_filename(self, data, zone_data):
        """
        data: 10.11.0,
        zone_data: {
            'zone_data': {
                'forward': [
                    {'acme-inc.local': {
                        'filename': 'acme-inc.local',
                        'sha256': 'df1710b930ae6d3afc4fb530acf583d0aaad09e57b5e8442fca9a7265f2ffdef',
                        'serial': '1775380015'}
                    }
                ],
                'reverse': [
                    {'10.11.0': {'filename': '0.11.10.in-addr.arpa', 'sha256': 'None', 'serial': 'None', 'network': '10.11.0'}}
                ]
            },
            'failed': False,
            'changed': False
        }

        # ------
        data: {
            'name': 'acme-inc.local', 'type': 'primary', 'state': 'present', 'create_forward_zones': True, 'create_reverse_zones': True,
            'update_policy': {'mode': 'rules',
                'rules': [
                    {'action': 'grant', 'identity': 'ddns-host1',
                        'ruletype': 'name', 'name': 'host1.example.org.',
                        'types': ['A', 'TXT']
                    }, {
                        'action': 'grant', 'identity': 'ddns-host1',
                        'ruletype': 'name', 'name': '_acme-challenge.host1.example.org.',
                        'types': ['TXT']
                    }]},
            'networks': ['10.11.0'],
            'name_servers': ['ns1'],
            'hosts': [{'name': 'ns1', 'ip': '10.11.0.1'}, {'name': 'srv001', 'ip': '10.11.1.1', 'aliases': ['www']}]
        },
        zone_data: {
            'zone_data': {
                'forward': [
                    {'acme-inc.local': {'filename': 'acme-inc.local',
                        'sha256': 'df1710b930ae6d3afc4fb530acf583d0aaad09e57b5e8442fca9a7265f2ffdef',
                        'serial': '1775380015'}}
                ],
                'reverse': [
                    {'10.11.0': {'filename': '0.11.10.in-addr.arpa',
                        'sha256': '24cfbc3e3889ac955c8d0e0cc5ab0cdc06a341eab04253e4012ad38d02bca84d',
                        'serial': '1775464534', 'network': '10.11.0'}}
                ]
            },
            'failed': False,
            'changed': False
        }
        """
        display.v(f"bodsch.dns.zone_filename(data: {data}, zone_data: {zone_data})")

        result = None

        zone_data = zone_data.get("zone_data", {})

        display.v(f"  - zone_data: {zone_data}")

        item = {
            k: v
            for key, values in zone_data.items()
            for x in values
            for k, v in x.items()
            if k == data
        }

        display.v(f"  - item     : {item}")

        if item:
            result = list(item.values())[0].get("filename")

        display.v(f"= {result}")

        return result

    # def combine_zone_data(self, data, zone_data):
    #     """ """
    #     display.v(f"bodsch.dns.combine_zone_data(data: {data}, zone_data: {zone_data})")
    #
    #     result = dict()
    #
    #     _zone_data = zone_data.get("zone_data", {})
    #
    #     _forward_data = _zone_data.get("forward", None)
    #     _reverse_data = _zone_data.get("reverse", None)
    #
    #     display.v(f"  - forward: {_forward_data}")
    #     display.v(f"  - reverse: {_reverse_data}")
    #
    #     display.v(f"  - forward: {type(_forward_data)}")
    #
    #     forward_filenames = {
    #         k: v.get("filename") for x in _forward_data for k, v in x.items()
    #     }
    #     reverse_filenames = {
    #         k: v.get("filename") for x in _reverse_data for k, v in x.items()
    #     }
    #
    #     display.v(f"  - forward_filenames: {forward_filenames}")
    #
    #     for d in data:
    #         _name = d.get("name")
    #         display.v(f"  - name: {_name}")
    #
    #         if _name in forward_filenames.keys():
    #             display.v(f"    filename: {forward_filenames.get(_name).values()}")
    #
    #     return result

    def __append(self, data, domain=None):
        """
        append to evvery list element
        """
        # display.v(f"__append_dot({data})")
        # display.v(f"  - {type(data)}")

        if not len(data) > 0:
            return data

        if isinstance(data, list):
            try:
                for x in range(len(data)):
                    if not data[x][-1:] == ".":
                        if domain:
                            data[x] = f"{data[x]}.{domain}."
                        else:
                            data[x] = f"{data[x]}."
            except Exception:
                # display.v(f"  - {e} - {type(e)}")

                for i in data:
                    if not i.get("name")[-1:] == ".":
                        if domain:
                            i["name"] = f"{i['name']}.{domain}."
                        else:
                            i["name"] = f"{i['name']}."

                pass
        # display.v(f"= {data}")

        return data

    # def __reverse_dns(self, data):
    #     """
    #     """
    #     # display.v(f"__reverse_dns({data})")
    #     if self.__is_valid_ipv4(data):
    #         reverse_ip = ".".join(data.replace(data + '.', '').split('.')[::-1])
    #         reverse_ip += ".in-addr.arpa"
    #
    #         return reverse_ip
    #     else:
    #         try:
    #             _offset = None
    #             if data.count("/") == 1:
    #                 _prefix = data.split("/")[1]
    #                 _offset = int(9 + int(_prefix) // 2)
    #                 display.v(f" {_prefix} - {_offset}")
    #
    #             _network = netaddr.IPNetwork(str(data))
    #             _prefix = _network.prefixlen
    #             _ipaddress = netaddr.IPAddress(_network)
    #             reverse_ip = _ipaddress.reverse_dns
    #             if _offset:
    #                 reverse_ip = reverse_ip[-_offset:]
    #
    #             return reverse_ip
    #
    #         except Exception as e:
    #             display.v(f" ERROR: {e}")
    #             pass
    #
    #     return None

    def __hash(self, data):
        """ """
        result_str = str(data)
        _bytes = result_str.encode("utf-8")

        return hashlib.sha256(_bytes).hexdigest()

    # def __is_valid_ipv4(self, ip):
    #     """
    #         Validates IPv4 addresses.
    #     """
    #     pattern = re.compile(r"""
    #         ^
    #         (?:
    #           # Dotted variants:
    #           (?:
    #             # Decimal 1-255 (no leading 0's)
    #             [3-9]\d?|2(?:5[0-5]|[0-4]?\d)?|1\d{0,2}
    #           |
    #             0x0*[0-9a-f]{1,2}  # Hexadecimal 0x0 - 0xFF (possible leading 0's)
    #           |
    #             0+[1-3]?[0-7]{0,2} # Octal 0 - 0377 (possible leading 0's)
    #           )
    #           (?:                  # Repeat 0-3 times, separated by a dot
    #             \.
    #             (?:
    #               [3-9]\d?|2(?:5[0-5]|[0-4]?\d)?|1\d{0,2}
    #             |
    #               0x0*[0-9a-f]{1,2}
    #             |
    #               0+[1-3]?[0-7]{0,2}
    #             )
    #           ){0,3}
    #         |
    #           0x0*[0-9a-f]{1,8}    # Hexadecimal notation, 0x0 - 0xffffffff
    #         |
    #           0+[0-3]?[0-7]{0,10}  # Octal notation, 0 - 037777777777
    #         |
    #           # Decimal notation, 1-4294967295:
    #           429496729[0-5]|42949672[0-8]\d|4294967[01]\d\d|429496[0-6]\d{3}|
    #           42949[0-5]\d{4}|4294[0-8]\d{5}|429[0-3]\d{6}|42[0-8]\d{7}|
    #           4[01]\d{8}|[1-3]\d{0,9}|[4-9]\d{0,8}
    #         )
    #         $
    #     """, re.VERBOSE | re.IGNORECASE)
    #
    #     return pattern.match(ip) is not None
    #
    # def __is_valid_ipv6(self, ip):
    #     """
    #         Validates IPv6 addresses.
    #     """
    #     pattern = re.compile(r"""
    #         ^
    #         \s*                         # Leading whitespace
    #         (?!.*::.*::)                # Only a single whildcard allowed
    #         (?:(?!:)|:(?=:))            # Colon iff it would be part of a wildcard
    #         (?:                         # Repeat 6 times:
    #             [0-9a-f]{0,4}           #   A group of at most four hexadecimal digits
    #             (?:(?<=::)|(?<!::):)    #   Colon unless preceeded by wildcard
    #         ){6}                        #
    #         (?:                         # Either
    #             [0-9a-f]{0,4}           #   Another group
    #             (?:(?<=::)|(?<!::):)    #   Colon unless preceeded by wildcard
    #             [0-9a-f]{0,4}           #   Last group
    #             (?: (?<=::)             #   Colon iff preceeded by exacly one colon
    #              |  (?<!:)              #
    #              |  (?<=:) (?<!::) :    #
    #              )                      # OR
    #          |                          #   A v4 address with NO leading zeros
    #             (?:25[0-4]|2[0-4]\d|1\d\d|[1-9]?\d)
    #             (?: \.
    #                 (?:25[0-4]|2[0-4]\d|1\d\d|[1-9]?\d)
    #             ){3}
    #         )
    #         \s*                         # Trailing whitespace
    #         $
    #     """, re.VERBOSE | re.IGNORECASE | re.DOTALL)
    #
    #     return pattern.match(ip) is not None

    # def when_reverse_zone(self, data, host_all_addresses: list = []):
    #     """
    #     (item.1 | bodsch.dns.zone_filename(bind_zone_data) | string | length > 0) and
    #     (item.state | default('present') == 'present') and
    #     (item.create_reverse_zones | default('true') | bool) and
    #     (
    #         (item[0].type is defined and item[0].type == 'primary') or
    #         (item[0].type is not defined and item[0].primaries is defined and
    #         (host_all_addresses | intersect(item[0].primaries) | length > 0))
    #     )
    #
    #     data:
    #         [
    #             {   'name': 'acme-inc.local', 'type': 'primary', 'create_forward_zones': True,
    #                 'create_reverse_zones': True,
    #                 'update_policy': {'mode': 'rules', 'rules': [
    #                     {'action': 'grant', 'identity': 'ddns-host1', 'ruletype': 'name', 'name': 'host1.example.org.', 'types': ['A', 'TXT']},
    #                     {'action': 'grant', 'identity': 'ddns-host1', 'ruletype': 'name', 'name': '_acme-challenge.host1.example.org.', 'types': ['TXT']}
    #                 ]},
    #                 'name_servers': ['ns1'],
    #                 'hosts': [
    #                     {'name': 'ns1', 'ip': '10.11.0.1'}, {'name': 'srv001', 'ip': '10.11.1.1', 'aliases': ['www']}
    #                 ]
    #             },
    #             '10.11.0'
    #         ]
    #     """
    #     display.v(
    #         f"bodsch.dns.when_reverse_zone(data: {data}, host_all_addresses: {host_all_addresses})"
    #     )
    #     # display.v("-----")
    #
    #     item_0 = data[0]
    #     # item_1 = data[1]
    #
    #     # display.v(f" - 0: {item_0}")
    #     # display.v(f" - 1: {item_1}")
    #
    #     zone_type = item_0.get("type", None)
    #     zone_primaries = item_0.get("primaries", [])
    #     zone_state = item_0.get("state", "present")
    #     create_reverse_zones = item_0.get("create_reverse_zones", None)
    #
    #     # display.v(f" - type     : {zone_type}")
    #     # display.v(f" - primaries: {zone_primaries}")
    #     # display.v(f" - state    : {zone_state}")
    #     # display.v(f" - create_reverse_zones: {create_reverse_zones}")
    #
    #     # display.v("-----")
    #     # display.v(f" - zone_primaries    : {zone_primaries}")
    #     # display.v(f" - host_all_addresses: {host_all_addresses}")
    #
    #     _intersect = intersect(left=zone_primaries, right=host_all_addresses)
    #
    #     # display.v(f" - intersect: {_intersect}")
    #
    #     if zone_state == "present" or len(_intersect) > 0:
    #         result = True
    #     else:
    #         result = False
    #
    #     display.v(f"= {result}")
    #
    #     return result


def intersect(left: list[T], right: list[T]) -> list[T]:
    """Return the unique elements that exist in both input lists.

    Args:
        left: First list of values.
        right: Second list of values.

    Returns:
        A list with the unique common elements of both inputs.

    Notes:
        The elements must be hashable at runtime because a set-based
        implementation is used.
        The result order is not guaranteed.
    """
    return list(set(left).intersection(right))
