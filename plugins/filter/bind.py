# python 3 headers, required if submitting to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.utils.display import Display
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
            'zone_data': self.zone_data,
            'reverse_zone_data': self.reverse_zone_data,
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

    def zone_serial(self, data, zone_hash, exists_hashes, network):
        """
        """
        display.v(
            f"zone_serial({data}, {zone_hash}, {exists_hashes}, {network})")

        result = dict(
            hash=zone_hash,
            serial=int(time.time())
        )

        if isinstance(exists_hashes, list) and len(exists_hashes) > 0:
            for r in exists_hashes:
                display.v(f" - {r}")
                _network = r.get("network")

                if _network == network:
                    _hash = r.get("hash", None)
                    _serial = None

                    display.v(f"   - {_hash}")

                    if _hash:
                        # split string: '; Hash: 2b7871f417f5034fb83486b0147ef663f9b72893bfdd7eb754895cbfe4feca95 1702451711'
                        _, _, _hash, _serial = _hash.split(" ")
                        display.v(f"   - {_hash} | {_serial}")

                    if _serial:
                        result.update({"serial": _serial})

        display.v(f"  = {result}")

        return result

    def zone_data(self, data, soa, ansible_hostname):
        """
        """
        # display.v(f"zone_data({data}, {soa}, {ansible_hostname})")

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

        display.v(f"  = {result} - {result_hash}")

        return (result, result_hash)

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

        display.v(f"  = {result} - {result_hash}")
        return (result, result_hash)

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

        reverse_ip = reverse_ip[-(9 + _prefix // 2):]

        return reverse_ip

    def __hash(self, data):
        """
        """
        result_str = str(data)
        _bytes = result_str.encode('utf-8')

        return hashlib.sha256(_bytes).hexdigest()
