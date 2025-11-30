# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

from typing import Any, Dict, List, Optional, Tuple

from ansible_collections.bodsch.dns.plugins.module_utils.pihole.database import DataBase


class ClientManager(DataBase):
    """ """

    def __init__(self, module: any, database: str):
        """ """
        self.module = module

        super().__init__(module, database)

    def list_clients(self) -> List[Tuple[int, str, int]]:
        self.execute("SELECT id, ip, comment FROM client")
        return self.fetchall()

    def client_by_ip(self, ip: str) -> Optional[int]:
        return self.get_id_by_column("client", "ip", ip)

    def add_or_update_client(
        self, ip: str, comment: str = "", groups: List[str] = []
    ) -> Dict[str, Any]:
        changed = False
        client_id = self.client_by_ip(ip)

        if client_id:
            # Check ob Kommentar sich geändert hat
            current_comment = self.get_client_comment(client_id)
            if current_comment != comment:
                self.execute(
                    "UPDATE client SET comment = ? WHERE id = ?", (comment, client_id)
                )
                changed = True
        else:
            self.execute(
                "INSERT INTO client (ip, comment) VALUES (?, ?)", (ip, comment)
            )
            client_id = self.cursor.lastrowid
            changed = True

        # Vergleiche Gruppenzugehörigkeit
        current_group_ids = self.get_client_groups(client_id)

        # Ermittele Ziel-Group-IDs
        target_group_ids = []
        for group in groups:
            group_id = self.get_id_by_column("group", "name", group)
            if group_id is not None:
                target_group_ids.append(group_id)

        target_group_ids.sort()

        if current_group_ids != target_group_ids:
            self.execute(
                "DELETE FROM client_by_group WHERE client_id = ?", (client_id,)
            )
            for gid in target_group_ids:
                self.execute(
                    "INSERT INTO client_by_group (client_id, group_id) VALUES (?, ?)",
                    (client_id, gid),
                )
            changed = True

        if changed:
            self.commit()

        return dict(
            changed=changed,
            msg=f"Client '{ip}' {'updated' if changed else 'unchanged'}.",
        )

    def remove_client(self, ip: str) -> Dict[str, Any]:
        client_id = self.client_by_ip(ip)
        if not client_id:
            return dict(changed=False, msg=f"Client '{ip}' not found.")

        self.execute("DELETE FROM client WHERE id = ?", (client_id,))
        self.commit()
        return dict(changed=True, msg=f"Client '{ip}' removed.")

    def manage_clients(self, clients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        for c in clients:
            ip = c.get("ip")
            comment = c.get("comment", "")
            groups = c.get("groups", [])
            if not ip:
                continue
            results.append({ip: self.add_or_update_client(ip, comment, groups)})
        return results

    def get_client_comment(self, client_id: int) -> Optional[str]:
        self.execute("SELECT comment FROM client WHERE id = ?", (client_id,))
        row = self.fetchone()
        return row[0] if row else None

    def get_client_groups(self, client_id: int) -> List[int]:
        self.execute(
            "SELECT group_id FROM client_by_group WHERE client_id = ?", (client_id,)
        )
        return sorted(row[0] for row in self.fetchall())
