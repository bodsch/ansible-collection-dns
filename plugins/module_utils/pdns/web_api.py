#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)

import fnmatch
import requests
# from collections import defaultdict

from ansible_collections.bodsch.dns.plugins.module_utils.pdns.utils import fqdn, build_rrset
from ansible_collections.bodsch.dns.plugins.module_utils.pdns.records import host_records, srv_records, mx_records, txt_records


class PowerDNSWebApi:
    """
    """

    def __init__(self, module, config):
        self.module = module

        server_id = config.get("server_id")
        api_key = config.get("api_key", None)
        webserver_address = config.get("webserver_address", None)
        webserver_port = config.get("webserver_port", 8081)

        self.headers = {
            "Accept": "application/json",
            "X-API-Key": api_key,
        }

        self.base_url = f'http://{webserver_address}:{webserver_port}/api/v1/servers/{server_id}/zones'

    def zone_data(self, zone):
        """
            Check if zone is configured in PowerDNS.
            Return kind of zone (native, master, slave) uppercased or None
        """
        self.module.log(msg=f"PowerDNSWebApi::zone_data({zone})")

        url = f"{self.base_url}/{zone}."

        self.module.log(msg=f"  - {url}")

        (status_code, response, json_response) = self.__call_url(url=url)

        if status_code in [200, 201]:
            return json_response

        return None

    def zone_exists(self, zone):
        """
            Check if zone is configured in PowerDNS.
            Return kind of zone (native, master, slave) uppercased or None
        """
        self.module.log(msg=f"PowerDNSWebApi::zone_exists({zone})")

        data = self.zone_data(zone)

        if isinstance(data, dict):
            kind = data.get('kind', None)

            if kind is not None:
                kind = kind.upper()

            return kind

        return None

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
            if zone is None or fnmatch.fnmatch(z.get('name'), zone_fqdn):
                list.append({
                    'name': z.get('name'),
                    'kind': z.get('kind').lower(),
                    'serial': z.get('serial'),
                })

        self.module.log(msg=f"= {list}")

        return list

    def extract_existing_rrsets(self, zone_data):
        """
        """
        self.module.log(msg=f"PowerDNSWebApi::extract_existing_rrsets({zone_data})")

        rrsets = {}
        for rr in zone_data.get('rrsets'):
            key = (rr.get('name'), rr.get('type'))

            contents = sorted([r.get('content') for r in rr.get('records') if not r.get('disabled')])

            rrsets[key] = {
                'ttl': rr.get('ttl'),
                'records': contents
            }
        return rrsets

    def build_full_rrsets(self, zone, data):
        """
        """
        self.module.log(msg=f"PowerDNSWebApi::build_full_rrsets({zone}, data)")

        rrsets = []
        rrsets += host_records(zone=zone, records=data.get('hosts', []))
        rrsets += srv_records(zone=zone, records=data.get('services', []))
        rrsets += mx_records(zone=zone, records=data.get('mail_servers', []))
        rrsets += txt_records(zone=zone, records=data.get('text', []))

        return rrsets

    def compare_rrsets(self, existing, desired):

        self.module.log("PowerDNSWebApi::compare_rrsets(existing, desired)")

        to_update = []

        for rr in desired:
            key = (rr.get('name'), rr.get('type'))
            existing_rr = existing.get(key)

            # self.module.log(f"  - {key}")
            # self.module.log(f"    `- {existing_rr}")

            new_contents = sorted([r.get('content') for r in rr.get('records')])
            existing_contents = existing_rr.get('records') if existing_rr else []

            # self.module.log(f"    `- {new_contents} vs. {existing_contents}")

            # Nur wenn Inhalte verschieden sind → REPLACE
            if set(new_contents) != set(existing_contents):
                # Baue das minimal nötige rrset (nicht pauschal desired übernehmen)
                rrset = {
                    'name': rr.get('name'),
                    'type': rr.get('type'),
                    'ttl': rr.get('ttl'),
                    'changetype': 'REPLACE',
                    'records': [
                        {'content': content, 'disabled': False}
                        for content in new_contents
                    ]
                }
                to_update.append(rrset)

        return to_update

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

    def zone_secondary(self, base_url, zone, masters, comment):
        """
            Add a new secondary zone to PowerDNS
        """        # kind = self.zone_exists(zone)
        # if kind == 'SLAVE':
        #     return False
        #
        # if kind == 'MASTER' or kind == 'NATIVE':
        #     self.module.log(msg="zone %s is %s. Cannot convert to slave" % (zone, kind))
        #
        # masters = masters.split(',')
        #
        # data = {
        #     'kind': 'secondary',
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

    def zone_primary(self, zone, soa, nameservers, comment, ttl=60, wantkind='Master'):
        """
            Add a new Master/Native zone to PowerDNS
        """
        self.module.log(msg=f"PowerDNSWebApi::zone_primary({zone}, {soa}, {nameservers}, {comment}, {ttl}, {wantkind})")

        kind = self.zone_exists(zone)

        zone_fqdn = zone if zone.endswith('.') else f"{zone}."

        if kind in ['MASTER', 'NATIVE']:
            return False

        status_code, msg, json_response = self.create_zone(zone, nameservers, kind=wantkind, masters=None)

        if status_code in [200, 201]:
            rrsets = [
                build_rrset(zone_fqdn, "SOA", ttl, [soa]),
                build_rrset(zone_fqdn, "NS", ttl, [fqdn(zone, x) for x in nameservers])
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

        (status_code, response, json_response) = self.__call_url(
            url=url,
            method='PATCH',
            payload=payload
        )

        self.module.log("------------------------------")
        self.module.log(f"  status  : {status_code}")
        self.module.log(f"  response: {json_response}")
        self.module.log("------------------------------")

        if status_code in [200, 201, 204]:
            msg = f"Zone {zone} at {url} successfully updated."
        else:
            msg = f"Failed to update zone {zone} at {url}: {json_response}."

        return status_code, msg, json_response

    # ---------------------------------------------------------------------------

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
                response = requests.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    verify=False
                )

            elif method == 'PATCH':
                response = requests.patch(
                    url,
                    headers=self.headers,
                    json=payload,
                    verify=False
                )

            elif method == "DELETE":
                response = requests.delete(
                    url,
                    headers=self.headers,
                    verify=False
                )

            else:
                self.module.log(msg=f"unsupported method: {method}")
                return (500, f"unsupported method: '{method}'", dict(error=f"unsupported method: {method}"))
                # pass

            response.raise_for_status()

            if response:
                try:
                    json_data = response.json()
                except Exception:
                    json_data = {}
                    pass

                return (response.status_code, response.text, json_data)

            return (response.status_code, response.text, response.json())

        except requests.exceptions.HTTPError as e:
            self.module.log(msg="ERROR (HTTPError)")
            self.module.log(msg=f"  - {e}")
            self.module.log(msg=f"  - url: {url}")
            self.module.log(msg=f"  - payload: {payload}")

            return (response.status_code, response.text, response.json())

        except ConnectionError as e:
            self.module.log(msg="ERROR (ConnectionError)")

            error_text = f"{type(e).__name__} {(str(e) if len(e.args) == 0 else str(e.args[0]))}"
            self.module.log(msg=f"  - {error_text}")

            return (500, error_text, {})

        except Exception as e:
            self.module.log(msg="ERROR (Exception)")
            error_text = f"{type(e).__name__}: {str(e)}"

            if response:
                try:
                    json_data = response.json()
                except Exception:
                    json_data = {}
                    pass

                return (response.status_code, response.text, json_data)

            else:
                return (500, error_text, {})
