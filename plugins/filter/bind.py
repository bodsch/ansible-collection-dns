# python 3 headers, required if submitting to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.utils.display import Display
import json
import netaddr
import hashlib
import time

display = Display()


class FilterModule(object):
    """
        Ansible file jinja2 tests
    """

    def filters(self):
        return {
            'zone_type': self.zone_type,
            'zone_serial': self.zone_serial,
            'forward_zone_data': self.forward_zone_data,
            'reverse_zone_data': self.reverse_zone_data,
            'zone_filename': self.zone_filename,
            'append_zone_filename': self.append_zone_filename,
        }

    def zone_type(self, data, all_addresses):
        """
        """
        # display.v(f"zone_type({data}, {all_addresses})")
        result = None
        _type = data.get("type", None)
        _primaries = data.get("primaries", None)
        _forwarders = data.get("forwarders", None)

        # display.v(f"  - type {_type}")
        # display.v(f"  - primaries {_primaries}")
        # display.v(f"  - forwarders {_forwarders}")

        if _type and _type in ["primary", "secondary", "forward"]:
            result = _type
            # display.v(f"  = {result}")

        elif not _type and _primaries:
            primaries_in_all_addresses = len(
                [x for x in all_addresses if x in _primaries]) > 0
            if primaries_in_all_addresses:
                result = "primary"
            else:
                result = "secondary"
            # display.v(f"  = {result}")

        elif not _type and _forwarders:
            result = "forward"
            # display.v(f"  = {result}")

        display.v(f"  = {result}")

        return result

    def zone_serial(self, domain, zone_hash, exists_hashes, network=None):
        """
            define serial for zone data or take existing serial when hash are equal

            input:
                domain:
                    - 'acme-inc.com'
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
                              'acme-inc.com': {
                                'filename': 'acme-inc.com',
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
                    - 'acme-inc.com'
        """
        display.v(f"zone_serial({domain}, {zone_hash}, {exists_hashes}, {network})")

        result = dict(
            hash=zone_hash,
            serial=int(time.time())
        )
        domain_data = None

        if isinstance(exists_hashes, str):
            exists_hashes = json.loads(exists_hashes)

        zone_data = exists_hashes.get("zone_data", [])

        if network:
            hashes = zone_data.get("reverse", {})
            domain_data = [x for x in hashes for k,v in x.items() if k == network]
        else:
            hashes = zone_data.get("forward", {})
            domain_data = [x for x in hashes for k,v in x.items() if k == domain]

        if isinstance(domain_data, list) and len(domain_data) > 0:
            domain_data = domain_data[0]

            # display.v(f" domain_data : {domain_data} ({type(domain_data)})")

            if network:
                domain_data = domain_data.get(network)
            else:
                domain_data = domain_data.get(domain)

            # display.v(f" domain_data : {domain_data} ({type(domain_data)})")

        if domain_data and len(domain_data) > 0:
            _serial = domain_data.get("serial", "")

            if _serial and _serial != "None":
                result.update({"serial": _serial})

        display.v(f"  = {result}")

        return result

    def forward_zone_data(self, data, soa, ansible_hostname):
        """
        """
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
            other_name_servers = self.__append_dot(other_name_servers)

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

        # display.v("forward_zone_data")
        # display.v(f"  = forward_zone_data: {result}")
        # display.v(f"  = zone_hash        : {result_hash}")

        return dict(
            forward_zone_data=result,
            zone_hash=result_hash
        )

    def reverse_zone_data(self, data, soa, ansible_hostname):
        """
            input:
                data: [
                {
                  'name': 'molecule.lan', 'primaries': ['172.17.0.2'], 'name_servers': ['ns1.acme-inc.com.', 'ns2.acme-inc.com.'],
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
        # display.v(f"reverse_zone_data({data}, {soa}, {ansible_hostname})")

        revip = None

        if isinstance(data, list) and len(data) == 2:
            revip = data[1]
            data = data[0]

        result = dict()

        domain = data.get("name")
        hostmaster_email = data.get("hostmaster_email", None)
        soa_ns_server = data.get("name_servers", [])
        other_name_servers = data.get("other_name_servers", None)

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
            other_name_servers = self.__append_dot(other_name_servers)

        reverse_ip = self.__reverse_dns(revip)

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

        # display.v("reverse_zone_data")
        # display.v(f"  = reverse_zone_data: {result}")
        # display.v(f"  = zone_hash        : {result_hash}")

        return dict(
            reverse_zone_data=result,
            zone_hash=result_hash
        )

        #display.v(f"  = {result} - {result_hash}")
        #return (result, result_hash)

    def zone_filename(self, data, zone_data):
        """
            append to evvery list element
        """
        display.v(f"zone_filename({data}, {zone_data})")
        result = None

        zone_data = zone_data.get("zone_data", {})

        item = {k: v for key, values in zone_data.items() for x in values for k, v in x.items() if k == data }

        display.v(f"  - {item}")

        if item:
            result = list(item.values())[0].get("filename")

        display.v(f"= {result}")

        return result

    def append_zone_filename(self, data, zone_data):
        """
            append to evvery list element
        """
        display.v(f"zone_filename({data}, {zone_data})")
        result = None

        _data = data.copy()

        for i in data:
            display.v(f" - {i}")


        return _data

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

    def __reverse_dns(self, data):
        """
        """

        _network = netaddr.IPNetwork(str(data))
        _prefix = _network.prefixlen
        _ipaddress = netaddr.IPAddress(_network)
        reverse_ip = _ipaddress.reverse_dns

        display.v(f"  = ip address        : {_ipaddress}")
        display.v(f"  = reverse_ip        : {reverse_ip}")

        reverse_ip = reverse_ip[-(9 + _prefix // 2):]

        display.v(f"  = reverse_ip        : {reverse_ip}")

        return reverse_ip

    def __hash(self, data):
        """
        """
        result_str = str(data)
        _bytes = result_str.encode('utf-8')

        return hashlib.sha256(_bytes).hexdigest()
