#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
web_api.py

PowerDNS HTTP API wrapper used by the `bodsch.dns` Ansible collection.

This module provides a small client class (`PowerDNSWebApi`) to interact with the PowerDNS
Authoritative Server API (`/api/v1/servers/<server_id>/zones`).

Responsibilities:
    - Query zone information (exists, details, list).
    - Create zones and patch RRsets via the PowerDNS API.
    - Build desired RRsets from higher-level structures using record helper functions
      (`host_records`, `srv_records`, `mx_records`, `txt_records`, optionally `ptr_records`).
    - Compare existing RRsets to desired RRsets and compute minimal PATCH payloads.

Notes:
    - The class expects an Ansible-like `module` object providing `module.log(...)` for logging.
    - TLS verification is disabled (`verify=False`) for POST/PATCH/DELETE calls as in the original code.
      If you need secure TLS, pass `https://...` and enable verification.
"""

from __future__ import absolute_import, print_function

import fnmatch
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import requests
from ansible_collections.bodsch.dns.plugins.module_utils.pdns.records import (
    host_records,
    mx_records,
    ptr_records,
    srv_records,
    txt_records,
)
from ansible_collections.bodsch.dns.plugins.module_utils.pdns.utils import (
    build_rrset,
    fqdn,
)

JsonType = Any
RRset = Dict[str, Any]
RRsetKey = Tuple[str, str]  # (name, type)
ExistingRRsets = Dict[RRsetKey, Dict[str, Any]]
CallUrlResult = Tuple[int, str, JsonType]
ZoneCreateResult = Tuple[int, str, JsonType]
ZonePatchResult = Tuple[int, str, JsonType]


class PowerDNSWebApi:
    """
    PowerDNS API client for zones and RRset management.

    The class wraps common PowerDNS zone operations and provides helper methods
    to build and compare RRsets.

    Attributes:
        module: An Ansible-like module object used for logging (must provide `log()`).
        headers: HTTP headers used for PowerDNS API calls.
        base_url: Base URL for zone operations:
            `http://<webserver_address>:<port>/api/v1/servers/<server_id>/zones`
    """

    def __init__(self, module: Any, config: Mapping[str, Any]) -> None:
        """
        Initialize the API client.

        Args:
            module: An Ansible-like module object used for logging.
            config: Client configuration. Expected keys:
                - server_id (str): PowerDNS server id (e.g. "localhost").
                - api_key (str): PowerDNS API key.
                - webserver_address (str): Host/IP where the API is reachable.
                - webserver_port (int): API port (default 8081).

        Returns:
            None
        """
        self.module = module
        self.module.log(f"PowerDNSWebApi::__init__(config={config})")

        server_id = config.get("server_id")
        api_key = config.get("api_key", None)
        webserver_address = config.get("webserver_address", None)
        webserver_port = config.get("webserver_port", 8081)

        self.headers: Dict[str, str] = {
            "Accept": "application/json",
            "X-API-Key": str(api_key) if api_key is not None else "",
        }

        self.base_url: str = (
            f"http://{webserver_address}:{webserver_port}/api/v1/servers/{server_id}/zones"
        )

    def zone_data(self, zone: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve full zone data from PowerDNS.

        Args:
            zone: Zone name (e.g. "example.com" or "example.com.").

        Returns:
            Optional[dict[str, Any]]:
                - Zone JSON object if the zone exists and the API returns HTTP 200/201.
                - None if the zone does not exist or the request fails.
        """
        self.module.log(msg=f"PowerDNSWebApi::zone_data({zone})")

        url = f"{self.base_url}/{zone}."
        self.module.log(msg=f"  - {url}")

        status_code, _response_text, json_response = self.__call_url(url=url)

        if status_code in (200, 201) and isinstance(json_response, dict):
            return json_response

        return None

    def zone_exists(self, zone: str) -> Optional[str]:
        """
        Check whether a zone exists in PowerDNS and return its kind.

        Args:
            zone: Zone name.

        Returns:
            Optional[str]:
                - Uppercased zone kind (e.g. "NATIVE", "MASTER", "SLAVE") if present.
                - None if the zone does not exist or kind is not available.
        """
        self.module.log(msg=f"PowerDNSWebApi::zone_exists({zone})")

        data = self.zone_data(zone)

        if isinstance(data, dict):
            kind = data.get("kind", None)
            return kind.upper() if isinstance(kind, str) else None

        return None

    def zone_list(self, zone: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List zones from PowerDNS, optionally filtered by a fnmatch pattern.

        Args:
            zone: Optional zone filter pattern (fnmatch).
                Examples:
                    - None: list all zones
                    - "example.com": match only example.com.
                    - "*.example.com": match sub-zones, depending on PowerDNS zone names

        Returns:
            list[dict[str, Any]]: A list of dicts containing:
                - name (str)
                - kind (str, lowercased)
                - serial (int | None)
        """
        self.module.log(msg=f"PowerDNSWebApi::zone_list({zone})")

        zone_fqdn: Optional[str] = None
        if isinstance(zone, str) and zone:
            zone_fqdn = zone if zone.endswith(".") else f"{zone}."

        result: List[Dict[str, Any]] = []
        url = f"{self.base_url}"

        status_code, _response_text, json_response = self.__call_url(url=url)

        if status_code != 200:
            self.module.log(msg=f"failed to enumerate zones at {url}: {json_response}")
            return result

        if not isinstance(json_response, list):
            return result

        for z in json_response:
            if not isinstance(z, dict):
                continue
            if zone_fqdn is None or fnmatch.fnmatch(str(z.get("name", "")), zone_fqdn):
                kind = z.get("kind")
                result.append(
                    {
                        "name": z.get("name"),
                        "kind": str(kind).lower() if kind is not None else "",
                        "serial": z.get("serial"),
                    }
                )

        return result

    def extract_existing_rrsets(self, zone_data: Mapping[str, Any]) -> ExistingRRsets:
        """
        Extract relevant RRset state (ttl + enabled record contents) from a zone JSON object.

        Args:
            zone_data: Zone JSON object as returned by :meth:`zone_data`.

        Returns:
            dict[tuple[str, str], dict[str, Any]]:
                Mapping (rrset_name, rrset_type) -> {"ttl": int, "records": list[str]}
                Only records with `disabled == False` are included.
        """
        self.module.log(msg=f"PowerDNSWebApi::extract_existing_rrsets({zone_data})")

        rrsets: ExistingRRsets = {}
        for rr in zone_data.get("rrsets", []) or []:
            if not isinstance(rr, dict):
                continue

            name = rr.get("name")
            rtype = rr.get("type")
            if not isinstance(name, str) or not isinstance(rtype, str):
                continue

            key: RRsetKey = (name, rtype)

            records = rr.get("records", []) or []
            contents = sorted(
                [
                    r.get("content")
                    for r in records
                    if isinstance(r, dict)
                    and not r.get("disabled")
                    and r.get("content") is not None
                ]
            )

            rrsets[key] = {"ttl": rr.get("ttl"), "records": contents}

        return rrsets

    def build_full_rrsets(self, zone: str, data: Mapping[str, Any]) -> List[RRset]:
        """
        Build the desired RRset list for a zone based on structured input.

        The following keys are supported in `data`:
            - hosts: list[dict] -> A/AAAA/CNAME (and PTR optionally)
            - services: list[dict] -> SRV
            - mail_servers: list[dict] -> MX
            - text: list[dict] -> TXT
            - create_forward_zones: bool -> if True, also build PTR rrsets from hosts

        Args:
            zone: Forward zone name.
            data: Structured record definition container.

        Returns:
            list[RRset]: List of RRset dictionaries (PowerDNS API format).
        """
        self.module.log(msg=f"PowerDNSWebApi::build_full_rrsets({zone}, data)")

        rrsets: List[RRset] = []
        rrsets += host_records(zone=zone, records=data.get("hosts", []))
        rrsets += srv_records(zone=zone, records=data.get("services", []))
        rrsets += mx_records(zone=zone, records=data.get("mail_servers", []))
        rrsets += txt_records(zone=zone, records=data.get("text", []))

        if bool(data.get("create_forward_zones", False)):
            rrsets += ptr_records(zone=zone, records=data.get("hosts", []))

        return rrsets

    def compare_rrsets(
        self, existing: ExistingRRsets, desired: Sequence[RRset]
    ) -> List[RRset]:
        """
        Compare existing RRsets with desired RRsets and compute minimal REPLACE updates.

        For each desired rrset:
            - Compare enabled record contents (set-wise).
            - If different from existing, create a minimal rrset payload with:
                changetype="REPLACE" and records=[{"content": ..., "disabled": False}, ...]

        Args:
            existing: Existing RRset snapshot as produced by :meth:`extract_existing_rrsets`.
            desired: Desired RRsets (PowerDNS API rrset dicts).

        Returns:
            list[RRset]: List of rrset PATCH entries that must be sent to PowerDNS.
        """
        self.module.log("PowerDNSWebApi::compare_rrsets(existing, desired)")

        to_update: List[RRset] = []

        for rr in desired:
            key: RRsetKey = (str(rr.get("name")), str(rr.get("type")))
            existing_rr = existing.get(key)

            new_contents = sorted(
                [r.get("content") for r in rr.get("records", []) if isinstance(r, dict)]
            )
            existing_contents = existing_rr.get("records") if existing_rr else []

            if set(new_contents) != set(existing_contents):
                rrset: RRset = {
                    "name": rr.get("name"),
                    "type": rr.get("type"),
                    "ttl": rr.get("ttl"),
                    "changetype": "REPLACE",
                    "records": [
                        {"content": content, "disabled": False}
                        for content in new_contents
                    ],
                }
                to_update.append(rrset)

        return to_update

    def zone_delete(self, base_url: str, zone: str) -> bool:
        """
        Delete a zone in PowerDNS.

        This method is currently a stub (original code commented-out).

        Args:
            base_url: Base URL for zones (unused in current implementation).
            zone: Zone name (unused in current implementation).

        Returns:
            bool: Always False (not implemented).
        """
        _ = base_url
        _ = zone
        return False

    def zone_secondary(
        self, base_url: str, zone: str, masters: str, comment: str
    ) -> bool:
        """
        Create a secondary (slave) zone.

        This method is currently a stub (original code commented-out).

        Args:
            base_url: Base URL for zones (unused in current implementation).
            zone: Zone name (unused in current implementation).
            masters: Comma-separated master IP list (unused in current implementation).
            comment: Comment string (unused in current implementation).

        Returns:
            bool: Always False (not implemented).
        """
        _ = base_url
        _ = zone
        _ = masters
        _ = comment
        return False

    def zone_primary(
        self,
        zone: str,
        soa: str,
        nameservers: Sequence[str],
        comment: str,
        ttl: int = 60,
        wantkind: str = "Master",
    ) -> bool:
        """
        Create a primary zone (Master/Native) and apply initial SOA+NS rrsets.

        Workflow:
            - If the zone already exists as MASTER/NATIVE: returns False.
            - Else:
                - Create the zone via :meth:`create_zone`.
                - PATCH initial rrsets (SOA + NS) via :meth:`patch_zone`.
                - Returns True (indicates an attempt was made).

        Args:
            zone: Zone name.
            soa: SOA content string.
            nameservers: Nameserver hostnames (will be fqdn()'d).
            comment: Comment string (currently only used in logs; not applied to rrsets here).
            ttl: TTL for initial SOA/NS rrsets.
            wantkind: "Master" or "Native" (PowerDNS kind title-cased internally).

        Returns:
            bool:
                - False if the zone already exists as MASTER/NATIVE.
                - True if a create+patch attempt was performed (even if patch fails).
        """
        self.module.log(
            msg=f"PowerDNSWebApi::zone_primary({zone}, {soa}, {nameservers}, {comment}, {ttl}, {wantkind})"
        )

        kind = self.zone_exists(zone)
        zone_fqdn = zone if zone.endswith(".") else f"{zone}."

        if kind in ("MASTER", "NATIVE"):
            return False

        status_code, _msg, _json_response = self.create_zone(
            zone, nameservers, kind=wantkind, masters=None
        )

        if status_code in (200, 201):
            rrsets = [
                build_rrset(zone_fqdn, "SOA", ttl, [soa]),
                build_rrset(zone_fqdn, "NS", ttl, [fqdn(zone, x) for x in nameservers]),
            ]
            self.patch_zone(zone, rrsets)

        return True

    def create_zone(
        self,
        zone: str,
        nameservers: Optional[Sequence[str]],
        kind: str = "Native",
        masters: Optional[Union[str, Sequence[str]]] = None,
    ) -> ZoneCreateResult:
        """
        Create a zone in PowerDNS.

        Args:
            zone: Zone name (without trailing dot is accepted).
            nameservers: Nameserver hostnames. Dots are normalized to trailing-dot form.
            kind: Zone kind (e.g. "Native", "Master", "Slave").
            masters: Optional masters list for secondary zones. Supported forms:
                - comma-separated string
                - sequence of strings

        Returns:
            tuple[int, str, Any]: (status_code, message, json_response)
                status_code: HTTP status code returned by PowerDNS.
                message: Human-readable status message.
                json_response: Parsed JSON response (type depends on API).
        """
        self.module.log(
            msg=f"PowerDNSWebApi::create_zone({zone}, {nameservers}, {masters}, {kind})"
        )

        zone_fqdn = zone if zone.endswith(".") else f"{zone}."

        ns_list: List[str] = []
        for ns in nameservers or []:
            if not isinstance(ns, str) or not ns:
                continue
            ns_list.append(ns if ns.endswith(".") else f"{ns}.")

        master_list: List[str] = []
        if masters:
            if isinstance(masters, str):
                master_list = [m.strip() for m in masters.split(",") if m.strip()]
            else:
                master_list = [str(m).strip() for m in masters if str(m).strip()]

        data: Dict[str, Any] = {
            "kind": str(kind).lower().title(),
            "masters": master_list,
            "name": zone_fqdn,
            "nameservers": ns_list,
        }

        url = f"{self.base_url}"
        status_code, _response_text, json_response = self.__call_url(
            url=url, method="POST", payload=data
        )

        if status_code not in (200, 201):
            msg = f"Failed to create zone {zone} at {url}: {json_response}."
        else:
            msg = f"Zone {zone} at {url} successfully created."

        return status_code, msg, json_response

    def patch_zone(self, zone: str, rrsets: Sequence[RRset]) -> ZonePatchResult:
        """
        Patch a zone by sending RRset modifications (typically REPLACE operations).

        Args:
            zone: Zone name (without trailing dot is accepted).
            rrsets: Sequence of rrset patch entries.

        Returns:
            tuple[int, str, Any]: (status_code, message, json_response)
                status_code: HTTP status code returned by PowerDNS.
                message: Human-readable status message.
                json_response: Parsed JSON response (type depends on API).
        """
        self.module.log(msg=f"PowerDNSWebApi::patch_zone({zone}, {rrsets})")

        zone_fqdn = zone if zone.endswith(".") else f"{zone}."
        url = f"{self.base_url}/{zone_fqdn}"
        payload: Dict[str, Any] = {"rrsets": list(rrsets)}

        status_code, _response_text, json_response = self.__call_url(
            url=url, method="PATCH", payload=payload
        )

        self.module.log("------------------------------")
        self.module.log(f"  status  : {status_code}")
        self.module.log(f"  response: {json_response}")
        self.module.log("------------------------------")

        if status_code in (200, 201, 204):
            msg = f"Zone {zone} at {url} successfully updated."
        else:
            msg = f"Failed to update zone {zone} at {url}: {json_response}."

        return status_code, msg, json_response

    # ---------------------------------------------------------------------------

    def __call_url(
        self,
        url: str,
        method: str = "GET",
        payload: Optional[Mapping[str, Any]] = None,
    ) -> CallUrlResult:
        """
        Perform an HTTP request to the PowerDNS API and return status, raw text and parsed JSON.

        Args:
            url: Full request URL.
            method: HTTP method ("GET", "POST", "PATCH", "DELETE").
            payload: Optional JSON payload for POST/PATCH.

        Returns:
            tuple[int, str, Any]: (status_code, response_text, json_response)
                status_code: HTTP status code (or 500 on local/client errors).
                response_text: Raw response body as text (or an error string on failures).
                json_response: Parsed JSON if possible, otherwise `{}`.

        Notes:
            - For unsupported methods this returns (500, ..., {"error": ...}).
            - For HTTP errors it returns the server's response status/text/json if available.
            - POST/PATCH/DELETE use `verify=False` as in the original implementation.
        """
        response: Optional[requests.Response] = None

        try:
            authentication: Tuple[()] = ()

            if method == "GET":
                response = requests.get(url, headers=self.headers, auth=authentication)

            elif method == "POST":
                response = requests.post(
                    url, headers=self.headers, json=payload, verify=False
                )

            elif method == "PATCH":
                response = requests.patch(
                    url, headers=self.headers, json=payload, verify=False
                )

            elif method == "DELETE":
                response = requests.delete(url, headers=self.headers, verify=False)

            else:
                self.module.log(msg=f"unsupported method: {method}")
                return (
                    500,
                    f"unsupported method: '{method}'",
                    {"error": f"unsupported method: {method}"},
                )

            response.raise_for_status()

            try:
                json_data: JsonType = response.json()
            except Exception:
                json_data = {}

            return response.status_code, response.text, json_data

        except requests.exceptions.HTTPError as e:
            self.module.log(msg="ERROR (HTTPError)")
            self.module.log(msg=f"  - {e}")
            self.module.log(msg=f"  - url: {url}")
            self.module.log(msg=f"  - payload: {payload}")

            if response is not None:
                try:
                    return response.status_code, response.text, response.json()
                except Exception:
                    return response.status_code, response.text, {}
            return 500, f"HTTPError: {e}", {}

        except ConnectionError as e:
            self.module.log(msg="ERROR (ConnectionError)")
            error_text = (
                f"{type(e).__name__} {(str(e) if len(e.args) == 0 else str(e.args[0]))}"
            )
            self.module.log(msg=f"  - {error_text}")
            return 500, error_text, {}

        except Exception as e:
            self.module.log(msg="ERROR (Exception)")
            error_text = f"{type(e).__name__}: {str(e)}"

            if response is not None:
                try:
                    return response.status_code, response.text, response.json()
                except Exception:
                    return response.status_code, response.text, {}

            return 500, error_text, {}
