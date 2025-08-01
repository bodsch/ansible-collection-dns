#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from ansible_collections.bodsch.core.plugins.module_utils.checksum import Checksum


class PiHole():
    """
    """
    # --- Klassenzustände & Regex ---
    _LINE_RE = re.compile(r"^\s*-\s+(?P<domain>\S+)(?:\s+\((?P<reason>[^)]+)\))?")
    _HEADER_RE = re.compile(r"^\s*\[\s*(?P<flag>[✓✗])\s*]")
    _COMMENT = "Domain already in the specified list"
    _ACTION_RE = re.compile(r"^(?P<action>Added|Failed to add)\s+\d+\s+domain\(s\):$")

    def __init__(self, module):
        self.module = module

        # self.module.log("PiHole::__init__()")

        self.pihole_bin = self.module.get_bin_path('pihole', False)
        self.pihole_ftl_bin = self.module.get_bin_path("pihole-FTL", False)

    def status(self):
        """
        """
        args = [self.pihole_bin]
        args.append("status")
        rc, out, err = self._exec(args)

        return rc

    def import_list(
        self,
        domains: List[str],
        list_type: str,
        comment: str
    ) -> Dict[str, Any]:
        """
        Importiert eine Allow- oder Deny-Liste.

        :param domains: Liste von Domain-Strings.
        :param list_type: "allow" oder "deny".
        :param comment: Kommentar, der an pihole übergeben wird.
        :returns: Dict mit Schlüsseln "changed", "added", "present".
        """
        # self.module.log(f"PiHole::import_list({domains}, {list_type}, {comment})")

        if list_type not in ("allow", "deny"):
            raise ValueError("list_type muss 'allow' oder 'deny' sein")

        cmd = [self.pihole_bin, list_type, *domains, "--comment", comment]
        rc, out, err = self._exec(cmd, check_rc=True)
        parsed = self._parse_output(out + "\n" + err)

        return {
            "changed": bool(parsed["added"]),
            "added": parsed["added"],
            # "duplicates": parsed["duplicates"],
            "present": parsed["present"],
        }

    def import_allow(self, domains: List[str], comment: str = "allowlist import"):
        return self.import_list(domains, "allow", comment)

    def import_deny(self, domains: List[str], comment: str = "denylist import"):
        return self.import_list(domains, "deny", comment)

    def admin_password(self, password: str):
        """
        """
        # self.module.log(f"PiHole::admin_password({password})")
        old_checksum = None
        cur_checksum = None

        checksum = Checksum(self.module)
        cur_checksum = checksum.checksum(password)

        _file = Path("/etc/pihole") / ".admin.checksum"

        if _file.exists():
            with open(_file, "r") as f:
                old_checksum = f.read().rstrip('\n')

        if old_checksum == cur_checksum:
            return dict(
                changed=False,
                failed=False,
                msg="This admin password has already been set."
            )

        args = [
            self.pihole_bin,
            "setpassword",
            password
        ]

        rc, out, err = self._exec(args)

        if rc == 0:
            with open(_file, "w") as f:
                f.write(cur_checksum)

            return dict(
                changed=True,
                failed=False,
                msg="The admin password has been successfully changed."
            )

        return dict(
            changed=False,
            failed=True,
            msg=err
        )

    def update_gravity(self):
        """
        """
        _changed = False

        args = [
            self.pihole_bin,
            "updateGravity"
        ]

        rc, out, err = self._exec(args)

        if rc == 0:

            # 'Status: No changes detected'
            m = re.search(r'(?m)(?<=Status:\s).*', out)
            if m:
                status = m.group(0)

            _changed = "no changes detected" not in status.strip().casefold()

            return dict(
                changed=_changed,
                failed=False,
                msg=status
            )

        return dict(
            changed=_changed,
            failed=True,
            msg="An error has occurred."
        )

    def reload_lists(self):
        return self.reload(command="reloadlists")

    def reload_dns(self):
        return self.reload(command="reloaddns")

    def reload(self, command: str = "reloadlists"):
        """
            reloaddns  : Update the lists and flush the cache without restarting the DNS server
            reloadlists: Update the lists WITHOUT flushing the cache or restarting the DNS server
        """
        _changed = False

        args = [
            self.pihole_bin,
            command
        ]

        rc, out, err = self._exec(args)

        if rc == 0:
            if command == "reloadlists":
                m = re.search(r'(?m)Reloading DNS lists.*', out)
                if m:
                    _changed = True
                    status = "DNS lists have been successfully reloaded."

            if command == "reloaddns":
                m = re.search(r'(?m)Flushing DNS cache.*', out)
                if m:
                    _changed = True
                    status = "Lists have been successfully reloaded."

            return dict(
                changed=_changed,
                failed=False,
                msg=status
            )

        return dict(
            changed=_changed,
            failed=True,
            msg="An error has occurred."
        )
    # -------------------

    def _exec(self, commands: List[str], check_rc: bool = True) -> Tuple[int, str, str]:
        """
        """
        # self.module.log(f"PiHole::_exec({commands}, {check_rc})")

        rc, out, err = self.module.run_command(commands, check_rc=check_rc)

        if rc != 0:
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")

        return rc, out, err

    def _parse_output(self, raw: str) -> Dict[str, List[str]]:
        """
        Parst die kombinierte Ausgabe aus stdout+stderr von `pihole allow|deny`.
        Liefert Dict mit Listen: "added", "duplicates", "invalid".
        """
        raw = re.sub(r"Logout attempt.*?Unauthorized!\n?", "", raw, flags=re.S)
        raw = re.sub(r"(?m)^/opt/pihole/api\.sh:.*readonly variable\n?", "", raw)

        # # self.module.log(f"PiHole::_parse_output({raw})")

        added: List[str] = []
        duplicates: List[str] = []
        present: List[str] = []

        current: Optional[List[str]] = None

        for line in raw.splitlines():
            line = line.strip()
            if not line or line == self._COMMENT:
                continue

            # Header-Zeile?
            hmatch = self._HEADER_RE.match(line)
            if hmatch:
                # Strip "[✓]" oder "[✗]" vor dem Text
                text = line[hmatch.end():].strip()
                m = self._ACTION_RE.match(text)
                if not m:
                    continue
                action = m.group("action")
                current = added if action == "Added" else []  # warn: temporär
                # Für „Failed to add“ bauen wir beide Ziel-Listen auf
                if action == "Failed to add":
                    # Wir entscheiden später beim individuellen Grund
                    current = None
                continue

            # Detail-Zeile?
            lmatch = self._LINE_RE.match(line)
            if not lmatch:
                continue

            dom = lmatch.group("domain")
            reason = (lmatch.group("reason") or "").lower()

            if current is added:
                added.append(dom)
            else:
                # fehlgeschlagene Domains aufteilen
                if "already" in reason or "exists" in reason:
                    duplicates.append(dom)
                else:
                    present.append(dom)

        return {
            "added": added,
            "duplicates": duplicates,
            "present": present,
        }
