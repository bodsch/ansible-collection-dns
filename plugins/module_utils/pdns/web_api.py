#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)

import fnmatch
import requests
from collections import defaultdict


class PowerDNSWebApi:
    """
    """
    def __init__(self, module, server_id, api_key, webserver_address, webserver_port=8081):
        self.module = module
        self.server_id = server_id

        self.headers = {
            "Accept": "application/json",
            "X-API-Key": api_key,
        }

        self.base_url = f'http://{webserver_address}:{webserver_port}/api/v1/servers/{self.server_id}/zones'

    def zone_exists(self, zone):
        """
            Check if zone is configured in PowerDNS.
            Return kind of zone (native, master, slave) uppercased or None
        """
        self.module.log(msg=f"PowerDNSWebApi::zone_exists({zone})")

        url = f"{self.base_url}/{zone}"

        (status_code, response, json_response) = self.__call_url(url=url)

        if status_code in [404, 422]:  # not found
            return None

        if status_code != 200:
            self.module.log(msg=f"failed to check zone {zone} at {url}: {json_response}")

        kind = json_response.get('kind', None)

        if kind is not None:
            kind = kind.upper()

        return kind

    def zone_list(self, zone=None):
        """
            Return list of existing zones
        """
        self.module.log(msg=f"PowerDNSWebApi::zone_list({zone})")
        zone_fqdn = zone if zone.endswith('.') else f"{zone}."

        list = []
        url = f"{self.base_url}"

        # response, info = fetch_url(url, headers=headers)
        (status_code, response, json_response) = self.__call_url(url=url)

        if status_code != 200:
            self.module.log(msg=f"failed to enumerate zones at {url}: {json_response}")

        self.module.log(msg=f"-> {json_response}")

        for z in json_response:
            if zone is None or fnmatch.fnmatch(z['name'], zone_fqdn):
                list.append({
                    'name': z['name'],
                    'kind': z['kind'].lower(),
                    'serial': z['serial'],
                })

        self.module.log(msg=f"= {list}")

        return list

    def zone_delete(self, base_url, zone):
        ''' Delete a zone in PowerDNS '''

        # url = "{0}/{1}".format(base_url, zone)
        #
        # response, info = fetch_url(url, headers=headers, method='DELETE')
        #
        # if info['status'] == 422:
        #     return False
        # if info['status'] != 200:
        #     self.module.log(msg="failed to delete zone %s at %s: %s" % (zone, url, info['msg']))

        return False

    def zone_add_slave(self, base_url, zone, masters, comment):
        """
            Add a new Slave zone to PowerDNS
        """
        # kind = self.zone_exists(zone)
        # if kind == 'SLAVE':
        #     return False
        #
        # if kind == 'MASTER' or kind == 'NATIVE':
        #     self.module.log(msg="zone %s is %s. Cannot convert to slave" % (zone, kind))
        #
        # masters = masters.split(',')
        #
        # data = {
        #     'kind': 'Slave',
        #     'masters': masters,
        #     'name': zone,
        #     'comments': [{
        #         'name': zone,
        #         'type': 'SOA',
        #         'account': '',
        #         'content': comment,
        #     }],
        # }
        # payload = json.dumps(data)
        #
        # response, info = fetch_url(base_url, data=payload, headers=headers, method='POST')
        # if info['status'] != 200:
        #     self.module.log(msg="failed to create slave zone %s at %s: %s" % (zone, base_url, info['msg']))

        return False

    def zone_add_master(self, zone, soa, nameservers, comment, ttl=60, wantkind='Master'):
        """
            Add a new Master/Native zone to PowerDNS
        """
        self.module.log(msg=f"PowerDNSWebApi::zone_add_master({zone}, {soa}, {nameservers}, {comment}, {ttl}, {wantkind})")

        kind = self.zone_exists(zone)

        zone_fqdn = zone if zone.endswith('.') else f"{zone}."

        self.module.log(msg=f" kind: {kind}")

        if kind in ['MASTER', 'NATIVE']:
            return False

        status_code, msg, json_response = self.create_zone(zone, nameservers, kind=wantkind, masters=None)

        if status_code in [200, 201]:
            rrsets = [
                self.build_rrset(zone_fqdn, "SOA", ttl, [soa]),
                self.build_rrset(zone_fqdn, "NS", ttl, [f"{x}.{zone_fqdn}" for x in nameservers])
            ]

            status_code, msg, json_response = self.patch_zone(zone, rrsets)

        return True

    def create_zone(self, zone, nameservers, kind="Native", masters=None):
        """
        """
        self.module.log(msg=f"PowerDNSWebApi::create_zone({zone}, {nameservers}, {masters}, {kind})")

        zone_fqdn = zone if zone.endswith('.') else f"{zone}."

        msg = None

        data = {
            'kind': str(kind).lower().title(),
            'masters': [],
            'name': zone_fqdn,
            'nameservers': [],
        }

        url = f"{self.base_url}"

        (status_code, response, json_response) = self.__call_url(url=url, method='POST', payload=data)

        if status_code not in [200, 201]:
            msg = f"Failed to create zone {zone} at {url}: {json_response}."
        else:
            msg = f"Zone {zone} at {url} successfully created."

        return status_code, msg, json_response

    def patch_zone(self, zone, rrsets):
        """
        """
        self.module.log(msg=f"PowerDNSWebApi::patch_zone({zone}, {rrsets})")
        zone_fqdn = zone if zone.endswith('.') else f"{zone}."

        url = f"{self.base_url}/{zone_fqdn}"

        payload = {"rrsets": rrsets}

        (status_code, response, json_response) = self.__call_url(url=url, method='PATCH', payload=payload)

        if status_code not in [200, 201, 204]:
            msg = f"Failed to update zone {zone} at {url}: {json_response}."
        else:
            msg = f"Zone {zone} at {url} successfully updated."

        return status_code, msg, json_response

    def add_records(self, zone, record_type="A", records=[], comment=None, account=None):
        """
        """
        self.module.log(msg=f"PowerDNSWebApi::add_records({zone}, {record_type}, {records}, {comment}, {account})")

        if record_type in ["A", "AAAA"]:
            rrsets = self._add_record_hst(zone=zone, records=records, comment=comment, account=account)

        if record_type in ["MX"]:
            rrsets = self._add_record_mx(zone=zone, records=records, comment=comment, account=account)

        if record_type in ["SRV"]:
            rrsets = self._add_record_srv(zone=zone, records=records, comment=comment, account=account)

        if record_type in ["TXT"]:
            rrsets = self._add_record_txt(zone=zone, records=records, comment=comment, account=account)

        # rrset = self.build_rrset(name, type, ttl, records, comment=comment, account=account)

        zone_fqdn = zone if zone.endswith('.') else f"{zone}."

        msg = None

        url = f"{self.base_url}/{zone_fqdn}"

        payload = {
            "rrsets": rrsets
        }

        (status_code, response, json_response) = self.__call_url(url=url, method='PATCH', payload=payload)

        if status_code not in [200, 201, 204]:
            msg = f"Failed to update zone {zone} at {url}: {json_response}."
        else:
            msg = f"Zone {zone} at {url} successfully updated."

        return status_code, msg, json_response

        # self.module.log(msg=f"failed to update zone {zone} at {url}: {json_response}")

    def build_rrset(self, name, rtype, ttl, records, changetype="REPLACE", comment=None, account=None):

        rrset = {
            "name": name if name.endswith('.') else f"{name}.",
            "type": rtype,
            "ttl": ttl,
            "changetype": changetype,
            "records": [
                {
                    "content": r if isinstance(r, str) else r["content"],
                    "disabled": False
                }
                for r in records
            ]
        }

        if comment:
            rrset["comments"] = [{
                "content": comment,
                "account": account or "",
            }]

        return rrset

    def fqdn(self, zone, name):
        """
            Wandelt Kurzformen in FQDNs um:
              - 'srv001' + 'acme-inc.com'     → 'srv001.acme-inc.com.'
              - 'srv001.acme-inc.com.'        → bleibt unverändert
              - '@' + 'acme-inc.com'          → 'acme-inc.com.'
        """
        if name == "@":
            return f"{zone}."  # root of the zone
        if name.endswith('.'):
            return name
        if name.endswith(zone):
            return f"{name}."

        return f"{name}.{zone}."

    def _add_record_hst(self, zone, records, comment, account):
        """
        """
        self.module.log(msg=f"PowerDNSWebApi::_add_record_hst({zone}, {records}, {comment}, {account})")

        rrsets = []

        if isinstance(records, list):

            for record in records:
                self.module.log(msg=f"  - record: {record})")
                # {'name': 'ns2', 'ip': '10.11.0.2'})
                # {'name': 'srv001', 'ip': '10.11.1.1', 'ipv6': '2001:db8::1', 'aliases': ['www']})

                name = record.get("name")
                ttl = record.get("ttl", 3600)
                ipv4 = record.get("ip", None)
                ipv6 = record.get("ipv6", None)
                aliases = record.get("aliases", None)

                if ipv6:
                    rrsets.append(
                        self.build_rrset(
                            name=self.fqdn(zone, name),
                            rtype="AAAA",
                            ttl=ttl,
                            records=[ipv6],
                            comment=comment if comment else ""
                        )
                    )

                if ipv4:
                    rrsets.append(
                        self.build_rrset(
                            name=self.fqdn(zone, name),
                            rtype="A",
                            ttl=ttl,
                            records=[ipv4],
                            comment=comment if comment else ""
                        )
                    )

                if aliases:
                    for a in aliases:
                        rrsets.append(
                            self.build_rrset(
                                name=self.fqdn(zone, a),
                                rtype="CNAME",
                                ttl=ttl,
                                records=[self.fqdn(zone, name)],
                                comment=comment if comment else ""
                            )
                        )

            self.module.log(msg=f"  - {rrsets}")

        return rrsets

    def _add_record_srv(self, zone, records, comment, account):
        """
            _service._proto.name.  TTL  IN SRV  priority weight port target
        """
        self.module.log(msg=f"PowerDNSWebApi::_add_record_srv({zone}, {records}, {comment}, {account})")

        rrsets = []
        zone_fqdn = zone if zone.endswith('.') else f"{zone}."

        grouped = defaultdict(list)

        for service in records:
            name = service["name"]
            grouped[name].append(service)

        for srv_name, entries in grouped.items():
            srv_records = []
            for entry in entries:
                priority = entry.get("priority", 0)
                weight = entry["weight"]
                port = entry["port"]
                target = self.fqdn(zone, entry["target"])

                srv_records.append({
                    "content": f"{priority} {weight} {port} {target}",
                    "disabled": False
                })

            rrsets.append(
                self.build_rrset(
                    name=f"{srv_name}.{zone_fqdn}",
                    rtype="SRV",
                    ttl=entry.get("ttl", 3600),
                    records=srv_records,
                    comment=comment if comment else ""
                )
            )

        return rrsets

    def _add_record_mx(self, zone, records, comment, account):
        """
        """
        self.module.log(msg=f"PowerDNSWebApi::_add_record_mx({zone}, {records}, {comment}, {account})")

        rrsets = []
        mx_records = []
        zone_fqdn = zone if zone.endswith('.') else f"{zone}."

        for record in records:
            name = record.get("name")
            ttl = record.get("ttl", 3600)
            preference = record.get("preference", 10)

            mx_records.append(
                dict(
                    content=self.fqdn(zone, f"{preference} {name}"),
                    disabled=False
                )
            )

        rrsets.append(
            self.build_rrset(
                name=zone_fqdn,
                rtype="MX",
                ttl=ttl,
                records=mx_records,
                comment=comment if comment else ""
            )
        )

        return rrsets

    def _add_record_txt(self, zone, records, comment, account):
        """
        """
        self.module.log(msg=f"PowerDNSWebApi::_add_record_txt({zone}, {records}, {comment}, {account})")

        rrsets = []

        for entry in records:
            name = entry.get("name")
            ttl = entry.get("ttl", 3600)
            txt_data = entry.get("text")

            # Normalisiere: Liste oder einzelner String
            if isinstance(txt_data, str):
                txt_data = [txt_data]

            txt_records = []
            for line in txt_data:
                # PowerDNS erwartet Text in doppelten Anführungszeichen
                quoted = f"\"{line}\""
                txt_records.append({
                    "content": quoted,
                    "disabled": False
                })

            fqdn_name = self.fqdn(zone, name)  # z. B. _kerberos.acme-inc.com.

            rrsets.append(
                self.build_rrset(
                    name=fqdn_name,
                    rtype="TXT",
                    ttl=ttl,
                    records=txt_records,
                    comment=comment or ""
                )
            )

        return rrsets

    def __call_url(self, url, method='GET', payload=None):
        """
        """
        response = None

        try:
            authentication = ()  # self.github_username, self.github_password)

            if method == "GET":
                response = requests.get(
                    url,
                    headers=self.headers,
                    auth=authentication
                )

            elif method == 'POST':
                # if isinstance(payload, str):
                #    paylod = json.dumps(payload)
                self.module.log(msg=f"= POST payload: {payload} ({type(payload)})")

                response = requests.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    verify=False
                )

                # response.raise_for_status()

            elif method == 'PATCH':
                # if isinstance(payload, str):
                #    payload = json.dumps(payload)
                self.module.log(msg=f"= PATCH payload: {payload} ({type(payload)})")

                response = requests.patch(
                    url,
                    headers=self.headers,
                    json=payload,
                    verify=False
                )

                # response.raise_for_status()

            elif method == "DELETE":
                response = requests.delete(
                    url,
                    headers=self.headers,
                    verify=False
                )

                # response.raise_for_status()

            else:
                self.module.log(msg=f"unsupported method: {method}")
                return (500, f"unsupported method: '{method}'", dict(error=f"unsupported method: {method}"))
                # pass

            response.raise_for_status()

            if response:
                self.module.log(msg="------------------------------------------------------------------")
                try:
                    self.module.log(msg=f" text    : {response.text} / {type(response.text)}")
                except Exception:
                    self.module.log(msg=" Exception - text    : <unavailable>")

                try:
                    json_data = response.json()
                except Exception:
                    json_data = {}
                    self.module.log(msg=" Exception - json    : <invalid JSON>")
                else:
                    self.module.log(msg=f" json    : {json_data} / {type(json_data)}")

                self.module.log(msg=f" code    : {response.status_code}")
                self.module.log(msg="------------------------------------------------------------------")

                return (response.status_code, response.text, json_data)

            # self.module.log(msg="------------------------------------------------------------------")
            # self.module.log(msg=f" text    : {response.text} / {type(response.text)}")
            # self.module.log(msg=f" json    : {response.json()} / {type(response.json())}")
            # # self.module.log(msg=f" headers : {response.headers}")
            # self.module.log(msg=f" code    : {response.status_code}")
            # self.module.log(msg="------------------------------------------------------------------")

            return (response.status_code, response.text, response.json())

        except requests.exceptions.HTTPError as e:
            self.module.log(msg="ERROR (HTTPError)")
            self.module.log(msg=f"  - {e}")

            # status_code = e.response.status_code
            # status_message = e.response.text

            self.module.log(msg="------------------------------------------------------------------")
            self.module.log(msg=f" text    : {response.text} / {type(response.text)}")
            self.module.log(msg=f" json    : {response.json()} / {type(response.json())}")
            # self.module.log(msg=f" headers : {response.headers}")
            self.module.log(msg=f" code    : {response.status_code}")
            self.module.log(msg="------------------------------------------------------------------")

            # self.module.log(msg=f" status_message : {status_code} {status_message}")
            # self.module.log(msg=f" status_message : {e.response.json()}")

            return (response.status_code, response.text, response.json())

        except ConnectionError as e:
            self.module.log(msg="ERROR (ConnectionError)")

            error_text = f"{type(e).__name__} {(str(e) if len(e.args) == 0 else str(e.args[0]))}"
            self.module.log(msg=f"  - {error_text}")

            self.module.log(msg="------------------------------------------------------------------")
            return (500, error_text, {})

        except Exception:
            self.module.log(msg="ERROR (Exception)")
            # error_text = f"{type(e).__name__}: {str(e)}"
            # self.module.log(msg=f"  - {error_text}")

            if response:
                self.module.log(msg="------------------------------------------------------------------")
                try:
                    self.module.log(msg=f" text    : {response.text} / {type(response.text)}")
                except Exception:
                    self.module.log(msg=" Exception - text    : <unavailable>")

                try:
                    json_data = response.json()
                except Exception:
                    json_data = {}
                    self.module.log(msg=" Exception - json    : <invalid JSON>")
                else:
                    self.module.log(msg=f" json    : {json_data} / {type(json_data)}")

                self.module.log(msg=f" code    : {response.status_code}")
                self.module.log(msg="------------------------------------------------------------------")

                return (response.status_code, response.text, json_data)

            else:
                return (500, error_text, {})
