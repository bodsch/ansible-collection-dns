#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2023-2025, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results
from ansible_collections.bodsch.dns.plugins.module_utils.pdns.config_loader import (
    PowerDNSConfigLoader,
)
from ansible_collections.bodsch.dns.plugins.module_utils.pdns.records import (
    build_ptr_rrsets_by_zone,
)
from ansible_collections.bodsch.dns.plugins.module_utils.pdns.utils import (
    build_rrset,
    fqdn,
    generate_serial,
)
from ansible_collections.bodsch.dns.plugins.module_utils.pdns.web_api import (
    PowerDNSWebApi,
)

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: pdns_zone_data
short_description: Synchronize PowerDNS forward zones and optional reverse (PTR) zones via the PowerDNS API
version_added: "0.9.0"
author:
  - Bodo Schulz (@bodsch) <bodo@boone-schulz.de>

description:
  - Reads PowerDNS configuration from the local PowerDNS configuration files to obtain API settings.
  - For each forward zone in C(zone_data), ensures the zone exists (creates it if missing) and synchronizes all RRsets.
  - Optionally creates and synchronizes reverse zones (IPv4/IPv6) and their PTR RRsets derived from the host definitions.
  - Changes are applied via the PowerDNS HTTP API (PATCH).

options:
  zone_data:
    description:
      - List of zone definitions to manage.
      - Each item describes a forward zone and its records, and can optionally trigger creation/sync of reverse PTR zones.
    type: raw
    required: true

notes:
  - Check mode is supported.
  - Requires the C(pdnsutil) binary on the target host; if not found, the module returns C(changed=false) with a message.
  - PowerDNS must have API enabled and reachable using the configuration loaded from the local PowerDNS configuration.

requirements:
  - PowerDNS authoritative server with API enabled.
  - C(pdnsutil) installed on the target host.
"""

EXAMPLES = r"""
- name: Manage a forward zone and records
  bodsch.dns.pdns_zone_data:
    zone_data:
      - name: example.com
        name_servers:
          - ns1.example.com
          - ns2.example.com
        hosts:
          - name: www
            type: A
            address: 203.0.113.10
          - name: api
            type: A
            address: 203.0.113.11
        records:
          - name: "@"
            type: MX
            ttl: 3600
            content:
              - "10 mail.example.com."
          - name: "@"
            type: TXT
            ttl: 3600
            content:
              - "v=spf1 -all"

- name: Manage forward zone and create reverse zones from hosts (PTR)
  bodsch.dns.pdns_zone_data:
    zone_data:
      - name: example.com
        name_servers:
          - ns1.example.com
          - ns2.example.com
        create_reverse_zones: true
        reverse_prefix_v4: 24
        reverse_prefix_v6: 64
        hosts:
          - name: host1
            address:
              - 192.0.2.10
              - "2001:db8::10"
          - name: host2
            address:
              - 192.0.2.11

- name: Use custom reverse SOA/NS timing values
  bodsch.dns.pdns_zone_data:
    zone_data:
      - name: example.com
        name_servers:
          - ns1.example.com
        create_reverse_zones: true
        reverse_zone_ttl: 3600
        reverse_zone_refresh: 10800
        reverse_zone_retry: 3600
        reverse_zone_expire: 604800
        reverse_zone_minimum: 3600
        hosts:
          - name: host1
            address:
              - 192.0.2.10
"""

RETURN = r"""
changed:
  description:
    - Whether any zone (forward and/or reverse) was changed.
  returned: always
  type: bool

failed:
  description:
    - Indicates failure (for example missing API configuration or API errors).
  returned: always
  type: bool

msg:
  description:
    - Per-zone results list. Each element contains a dict mapping zone name to its result.
  returned: always
  type: list
  elements: dict
  sample:
    - example.com:
        failed: false
        changed: true
        msg: "zone succesfully updated."
    - 2.0.192.in-addr.arpa:
        failed: false
        changed: false
        msg: "reverse zone is up-to-date."

rc:
  description:
    - Not returned by this module.
  returned: never
  type: int
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

        self.module.log("PdnsZoneData::__init__()")

        self.zone_data = module.params.get("zone_data")
        self._pdnsutil_bin = module.get_bin_path("pdnsutil", True)

    def run(self):
        """ """
        self.module.log("PdnsZoneData::run()")

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
            forward_zone = d.get("name")
            nameservers = d.get("name_servers", [])
            create_reverse_zones = bool(d.get("create_reverse_zones", False))
            reverse_prefix_v4 = d.get("reverse_prefix_v4", 24)
            reverse_prefix_v6 = d.get("reverse_prefix_v6", 64)

            self.module.log(f"  - {forward_zone}")

            res = {}

            # -----------------------------------------------------------------
            # forward zone
            # -----------------------------------------------------------------
            zone_rrsets = {}
            zone_data = pdns_api.zone_data(forward_zone)

            if zone_data:
                zone_rrsets = pdns_api.extract_existing_rrsets(zone_data)
            else:
                # keine zone vorhanden
                _ = self.create_zone(pdns_api, forward_zone, nameservers)
                zone_data = pdns_api.zone_data(forward_zone)
                if zone_data:
                    zone_rrsets = pdns_api.extract_existing_rrsets(zone_data)

            # prevent legacy PTR handling in PowerDNSWebApi.build_full_rrsets()
            d_forward = dict(d)
            d_forward["create_forward_zones"] = False

            zone_new_rrsets = pdns_api.build_full_rrsets(forward_zone, d_forward)
            rrset_changes = pdns_api.compare_rrsets(zone_rrsets, zone_new_rrsets)

            if rrset_changes:
                status_code, _, json_resp = pdns_api.patch_zone(
                    forward_zone, rrset_changes
                )

                if status_code in [200, 201, 204]:
                    res[forward_zone] = dict(
                        failed=False, changed=True, msg="zone succesfully updated."
                    )
                else:
                    res[forward_zone] = dict(failed=True, changed=False, msg=json_resp)
            else:
                res[forward_zone] = dict(
                    failed=False, changed=False, msg="zone is up-to-date."
                )

            # -----------------------------------------------------------------
            # reverse zones (PTR)
            # -----------------------------------------------------------------
            if create_reverse_zones:
                self.module.log("    create reverse zones")

                ptr_rrsets_by_zone = build_ptr_rrsets_by_zone(
                    forward_zone=forward_zone,
                    hosts=d.get("hosts", []),
                    prefix_v4=reverse_prefix_v4,
                    prefix_v6=reverse_prefix_v6,
                    comment="ansible automation",
                )

                for rev_zone, desired_ptr_rrsets in sorted(ptr_rrsets_by_zone.items()):
                    if not desired_ptr_rrsets:
                        continue

                    res[rev_zone] = self._sync_reverse_zone(
                        pdns_api,
                        rev_zone=rev_zone,
                        forward_zone=forward_zone,
                        nameservers=nameservers,
                        desired_ptr_rrsets=desired_ptr_rrsets,
                        cfg=d,
                    )

            result_state.append(res)

        _state, _changed, _failed, state, changed, failed = results(
            self.module, result_state
        )

        result = dict(changed=_changed, failed=_failed, msg=result_state)

        return result

    def pdns_config_loader(self):
        """ """
        self.module.log("PdnsZoneData::pdns_config_loader()")

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
        self.module.log(
            f"PdnsZoneData::create_zone(pdns_api={pdns_api}, zone={zone}, nameservers={nameservers})"
        )

        if isinstance(nameservers, list) and nameservers:
            ns = nameservers[0]
        else:
            ns = "nsX"

        serial = generate_serial()

        # ns darf short oder fqdn sein – fqdn sauber lassen, sonst an zone hängen
        if "." in ns:
            mname = ns if ns.endswith(".") else f"{ns}."
        else:
            mname = f"{ns}.{zone}."

        rname = f"hostmaster.{zone}."

        soa = f"{mname} {rname} {serial} 3600 1800 604800 86400"

        changed = pdns_api.zone_primary(
            zone=zone,
            soa=soa,
            nameservers=nameservers,
            ttl=640,
            comment="ansible automation",
            wantkind="native",
        )

        return changed

    def _normalize_reverse_nameservers_OLD(self, forward_zone, nameservers):
        """ """
        self.module.log(
            f"PdnsZoneData::_normalize_reverse_nameservers(forward_zone={forward_zone}, nameservers={nameservers})"
        )

        if not isinstance(nameservers, list) or len(nameservers) == 0:
            return [fqdn(forward_zone, "nsX")]

        normalized = []
        for ns in nameservers:
            # absolute external NS? keep, just ensure trailing dot
            if isinstance(ns, str) and ("." in ns) and (not ns.endswith(forward_zone)):
                normalized.append(ns if ns.endswith(".") else f"{ns}.")
            else:
                normalized.append(fqdn(forward_zone, ns))

        return normalized

    def _create_reverse_zone(self, pdns_api, reverse_zone, forward_zone, nameservers):
        """ """
        self.module.log(
            "PdnsZoneData::_create_reverse_zone(pdns_api=%s, reverse_zone=%s, forward_zone=%s, nameservers=%s)"
            % (pdns_api, reverse_zone, forward_zone, nameservers)
        )

        if isinstance(nameservers, list) and len(nameservers) > 0:
            primary_ns = str(nameservers[0])
        else:
            primary_ns = fqdn(forward_zone, "nsX")
            nameservers = [fqdn(forward_zone, "nsX")]

        if not primary_ns.endswith("."):
            primary_ns = f"{primary_ns}."

        rname = fqdn(forward_zone, "hostmaster")
        if not rname.endswith("."):
            rname = f"{rname}."

        serial = generate_serial()

        soa = f"{primary_ns} {rname} {serial} 3600 1800 604800 86400"
        self.module.log(f"  SOA: {soa}")

        return pdns_api.zone_primary(
            zone=reverse_zone,
            soa=soa,
            nameservers=nameservers,
            ttl=640,
            comment="ansible automation",
            wantkind="native",
        )

    def _reverse_nameservers(self, forward_zone, nameservers):
        """
        Reverse-Zonen müssen NS als FQDN der Forward-Zone bekommen
        (nicht ns1.<reverse-zone>).
        """
        self.module.log(
            f"PdnsZoneData::_reverse_nameservers(forward_zone={forward_zone}, nameservers={nameservers})"
        )

        if not isinstance(nameservers, list) or not nameservers:
            return [fqdn(forward_zone, "nsX")]

        out = []
        for ns in nameservers:
            if not isinstance(ns, str) or not ns:
                continue
            # Wenn bereits FQDN (oder extern), nur trailing dot erzwingen
            if "." in ns:
                out.append(ns if ns.endswith(".") else f"{ns}.")
            else:
                out.append(fqdn(forward_zone, ns))
        return out

    def ensure_reverse_zone_soa_ns(
        self,
        pdns_api,
        reverse_zone,
        forward_zone,
        nameservers,
        ttl=3600,
        refresh=10800,
        retry=3600,
        expire=604800,
        minimum=3600,
    ):
        """
        Stellt SOA/NS für Reverse-Zonen korrekt ein:
          SOA MNAME  = erster NS aus Forward-Zone (FQDN)
          SOA RNAME  = hostmaster.<forward-zone> (FQDN)
          Serial     = generate_serial(existing_serial)
        """
        self.module.log(
            f"PdnsZoneData::ensure_reverse_zone_soa_ns(pdns_api, reverse_zone, forward_zone, nameservers={nameservers}, ...)"
        )

        ns_fqdns = self._reverse_nameservers(forward_zone, nameservers)
        primary_ns = ns_fqdns[0].rstrip(".")
        rname = fqdn(forward_zone, "hostmaster").rstrip(".")

        zone_data = pdns_api.zone_data(reverse_zone)
        existing_serial = (
            zone_data.get("serial") if isinstance(zone_data, dict) else None
        )
        serial = generate_serial(existing_serial)

        soa = f"{primary_ns} {rname} {serial} {refresh} {retry} {expire} {minimum}"

        rrsets = [
            build_rrset(f"{reverse_zone}.", "SOA", ttl, [soa]),
            build_rrset(f"{reverse_zone}.", "NS", ttl, ns_fqdns),
        ]

        status_code, _, json_resp = pdns_api.patch_zone(reverse_zone, rrsets)

        if status_code not in [200, 201, 204]:
            return dict(failed=True, changed=False, msg=json_resp)

        return dict(failed=False, changed=True, msg="reverse SOA/NS updated.")

    # ----------------------------------------------------------------------------------------------

    @staticmethod
    def _strip_dot(value):
        return value[:-1] if isinstance(value, str) and value.endswith(".") else value

    def _normalize_reverse_nameservers(self, forward_zone, nameservers):
        """Reverse-Zonen müssen NS als FQDN der Forward-Zone bekommen."""
        if not isinstance(nameservers, list) or len(nameservers) == 0:
            return [fqdn(forward_zone, "nsX")]

        normalized = []
        for ns in nameservers:
            if not isinstance(ns, str) or not ns:
                continue

            # extern oder bereits fqdn -> nur trailing dot erzwingen
            if ("." in ns) and (not ns.endswith(forward_zone)):
                normalized.append(ns if ns.endswith(".") else f"{ns}.")
            else:
                normalized.append(fqdn(forward_zone, ns))

        return normalized

    def _extract_existing_soa_serial(self, zone_fqdn, existing_rrsets, zone_data=None):
        """Try SOA content first; fallback to zone_data.serial."""
        existing_rr = (
            existing_rrsets.get((zone_fqdn, "SOA")) if existing_rrsets else None
        )
        if existing_rr:
            records = existing_rr.get("records") or []
            if records:
                parts = str(records[0]).split()
                if len(parts) >= 3:
                    try:
                        return int(parts[2])
                    except Exception:
                        pass

        if isinstance(zone_data, dict):
            try:
                serial = zone_data.get("serial")
                return int(serial) if serial is not None else None
            except Exception:
                return None

        return None

    def _build_reverse_zone_soa_ns_rrsets(
        self,
        *,
        reverse_zone,
        forward_zone,
        nameservers,
        serial,
        ttl,
        refresh,
        retry,
        expire,
        minimum,
        comment="ansible automation",
    ):
        """Build desired SOA+NS rrsets for a reverse zone.

        PowerDNS expects SOA mname and rname as FQDNs with trailing dots.
        """
        zone_fqdn = reverse_zone if reverse_zone.endswith(".") else f"{reverse_zone}."

        ns_fqdns = self._normalize_reverse_nameservers(forward_zone, nameservers)

        primary_ns = ns_fqdns[0] if ns_fqdns[0].endswith(".") else f"{ns_fqdns[0]}."
        rname = fqdn(forward_zone, "hostmaster")
        rname = rname if rname.endswith(".") else f"{rname}."

        soa = f"{primary_ns} {rname} {int(serial)} {int(refresh)} {int(retry)} {int(expire)} {int(minimum)}"

        return [
            build_rrset(zone_fqdn, "SOA", int(ttl), [soa], comment=comment),
            build_rrset(zone_fqdn, "NS", int(ttl), ns_fqdns, comment=comment),
        ]

    def _sync_reverse_zone(
        self,
        pdns_api,
        *,
        rev_zone,
        forward_zone,
        nameservers,
        desired_ptr_rrsets,
        cfg,
    ):
        """One reverse-zone sync: SOA/NS + PTR, with serial bump only on changes."""
        ttl = int(cfg.get("reverse_zone_ttl", 3600))
        refresh = int(cfg.get("reverse_zone_refresh", 10800))
        retry = int(cfg.get("reverse_zone_retry", 3600))
        expire = int(cfg.get("reverse_zone_expire", 604800))
        minimum = int(cfg.get("reverse_zone_minimum", 3600))

        # ensure zone exists
        rev_zone_data = pdns_api.zone_data(rev_zone)
        if not rev_zone_data:
            ns_fqdns = self._normalize_reverse_nameservers(forward_zone, nameservers)
            _ = self._create_reverse_zone(
                pdns_api,
                reverse_zone=rev_zone,
                forward_zone=forward_zone,
                nameservers=ns_fqdns,
            )
            rev_zone_data = pdns_api.zone_data(rev_zone)

        if not rev_zone_data:
            return dict(
                failed=True,
                changed=False,
                msg="failed to read reverse zone after create",
            )

        existing_rrsets = pdns_api.extract_existing_rrsets(rev_zone_data)

        zone_fqdn = rev_zone if rev_zone.endswith(".") else f"{rev_zone}."
        base_serial = self._extract_existing_soa_serial(
            zone_fqdn, existing_rrsets, zone_data=rev_zone_data
        )
        if base_serial is None:
            base_serial = generate_serial()

        # baseline desired (keep current serial) to test if anything changes
        desired_soa_ns = self._build_reverse_zone_soa_ns_rrsets(
            reverse_zone=rev_zone,
            forward_zone=forward_zone,
            nameservers=nameservers,
            serial=base_serial,
            ttl=ttl,
            refresh=refresh,
            retry=retry,
            expire=expire,
            minimum=minimum,
        )
        desired_all = list(desired_soa_ns) + list(desired_ptr_rrsets)
        changes = pdns_api.compare_rrsets(existing_rrsets, desired_all)

        if not changes:
            return dict(failed=False, changed=False, msg="reverse zone is up-to-date.")

        # bump serial only if we actually change something
        new_serial = generate_serial(base_serial)
        desired_soa_ns_bumped = self._build_reverse_zone_soa_ns_rrsets(
            reverse_zone=rev_zone,
            forward_zone=forward_zone,
            nameservers=nameservers,
            serial=new_serial,
            ttl=ttl,
            refresh=refresh,
            retry=retry,
            expire=expire,
            minimum=minimum,
        )
        desired_all_bumped = list(desired_soa_ns_bumped) + list(desired_ptr_rrsets)
        changes_bumped = pdns_api.compare_rrsets(existing_rrsets, desired_all_bumped)

        status_code, _, json_resp = pdns_api.patch_zone(rev_zone, changes_bumped)

        if status_code in [200, 201, 204]:
            return dict(
                failed=False, changed=True, msg="reverse zone successfully updated."
            )

        return dict(failed=True, changed=False, msg=json_resp)


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
