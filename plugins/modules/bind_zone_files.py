#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""Ansible module to reconcile a batch of BIND zone files."""

from __future__ import annotations

import grp
import pwd
from dataclasses import asdict
from typing import Any

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.dns.plugins.module_utils.bind_zone.builder import (
    ZoneSpecBuilder,
)
from ansible_collections.bodsch.dns.plugins.module_utils.bind_zone.reconciler import (
    ZoneFileReconciler,
)

DOCUMENTATION = r"""
module: bind_zone_files
version_added: "1.0.0"
author:
  - "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"
short_description: Reconcile multiple BIND zone files in one module call

description:
  - Build canonical forward and reverse BIND zone files from raw zone data.
  - Compare rendered content against persisted files independent of the current SOA serial.
  - Increase the SOA serial only when the effective zone content changes.
  - Persist one JSON cache entry per managed zone file to support idempotence and purge.
  - Remove stale zone files that are no longer desired.

options:
  zones:
    description:
      - Raw zone definitions similar to C(bind_zones).
    required: true
    type: raw
    aliases:
      - zone_data
  zone_directory:
    description:
      - Directory where rendered zone files are stored.
    required: true
    type: str
  cache_directory:
    description:
      - Directory where one JSON cache file per managed zone file is stored.
    required: true
    type: str
  serial_strategy:
    description:
      - Strategy used to compute the next SOA serial when a zone changes.
    type: str
    choices:
      - unix
      - increment
    default: unix
  purge:
    description:
      - Remove zone files that are still tracked in cache but are no longer present in the desired input.
    type: bool
    default: true
  owner:
    description:
      - Optional file owner name.
    type: str
  group:
    description:
      - Optional file group name.
    type: str
  mode:
    description:
      - Optional file mode for written files.
    type: raw
    default: '0644'

attributes:
  check_mode:
    support: full
  diff_mode:
    support: full
"""

EXAMPLES = r"""
- name: Reconcile all BIND zone files in one module call
  bodsch.dns.bind_zone_files:
    zones: "{{ bind_zones }}"
    zone_directory: /etc/bind/zones
    cache_directory: /var/cache/ansible/bind-zones
    serial_strategy: unix
    purge: true
    owner: bind
    group: bind
    mode: "0644"

- name: Dry-run zone reconciliation
  bodsch.dns.bind_zone_files:
    zones: "{{ bind_zones }}"
    zone_directory: /etc/bind/zones
    cache_directory: /var/cache/ansible/bind-zones
  check_mode: true
"""

RETURN = r"""
changed:
  description: Indicates whether any zone file would change.
  returned: always
  type: bool
changes:
  description: Per-zone-file reconciliation result.
  returned: always
  type: list
  elements: dict
zone_files:
  description: Canonical zone file specs built from the raw input.
  returned: always
  type: list
  elements: dict
zone_definitions:
  description: Canonical zone definitions built from the raw input.
  returned: always
  type: list
  elements: dict
"""


class BindZoneFilesModule:
    """Implementation class for the bind_zone_files Ansible module."""

    def __init__(self, module: AnsibleModule) -> None:
        """Initialize the module wrapper."""
        self.module = module
        self._builder = ZoneSpecBuilder()
        self._reconciler = ZoneFileReconciler(
            zone_directory=self.module.params["zone_directory"],
            cache_directory=self.module.params["cache_directory"],
        )

    def run(self) -> dict[str, Any]:
        """Execute the module logic."""
        build_result = self._builder.build(self.module.params["zones"])
        owner_uid = self._resolve_user(self.module.params.get("owner"))
        owner_gid = self._resolve_group(self.module.params.get("group"))
        file_mode = self._normalize_mode(self.module.params.get("mode"))

        reconcile_result = self._reconciler.reconcile(
            zone_files=build_result.zone_files,
            serial_strategy=self.module.params["serial_strategy"],
            purge=self.module.params["purge"],
            check_mode=self.module.check_mode,
            file_mode=file_mode,
            owner_uid=owner_uid,
            owner_gid=owner_gid,
            include_diff=bool(getattr(self.module, "_diff", False)),
        )

        return {
            "changed": reconcile_result.changed,
            "zone_files": [asdict(item) for item in build_result.zone_files],
            "zone_definitions": [
                asdict(item) for item in build_result.zone_definitions
            ],
            "changes": [asdict(item) for item in reconcile_result.changes],
        }

    def _resolve_user(self, value: str | None) -> int | None:
        """Resolve a user name to a uid."""
        if value is None or str(value).strip() == "":
            return None
        try:
            return pwd.getpwnam(str(value)).pw_uid
        except KeyError as exc:
            self.module.fail_json(
                msg=f"Unknown owner user: {value!r}", exception=repr(exc)
            )
        raise AssertionError("unreachable")

    def _resolve_group(self, value: str | None) -> int | None:
        """Resolve a group name to a gid."""
        if value is None or str(value).strip() == "":
            return None
        try:
            return grp.getgrnam(str(value)).gr_gid
        except KeyError as exc:
            self.module.fail_json(
                msg=f"Unknown owner group: {value!r}", exception=repr(exc)
            )
        raise AssertionError("unreachable")

    def _normalize_mode(self, value: Any) -> int | None:
        """Normalize a file mode value."""
        if value is None or value == "":
            return None
        if isinstance(value, int):
            return value
        return int(str(value), 8)


def main() -> None:
    """Module entrypoint."""
    module = AnsibleModule(
        argument_spec={
            "zones": dict(required=True, type="raw", aliases=["zone_data"]),
            "zone_directory": dict(required=True, type="str"),
            "cache_directory": dict(
                required=False, type="str", default="~/.ansible/cache/bind"
            ),
            "serial_strategy": dict(
                required=False,
                type="str",
                default="unix",
                choices=["unix", "increment"],
            ),
            "purge": dict(required=False, type="bool", default=True),
            "owner": dict(required=False, type="str"),
            "group": dict(required=False, type="str"),
            "mode": dict(required=False, type="raw", default="0644"),
        },
        supports_check_mode=True,
    )

    try:
        result = BindZoneFilesModule(module).run()
    except Exception as exc:  # pragma: no cover - final guard for ansible execution
        module.fail_json(msg=str(exc), exception=repr(exc))

    module.exit_json(**result)


if __name__ == "__main__":
    main()
