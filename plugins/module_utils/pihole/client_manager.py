# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)
import sqlite3

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


class ClientManager():
    """
    """

    def __init__(self, module: any, database: str):
        """
        """
        self.module = module

        # self.module.log(f"ClientManager::__init__(module, database={database})")

        db_file = Path(database)

        if not db_file.exists():
            raise FileNotFoundError(f"Pi-hole DB not found at: {db_file}")

        self.conn = sqlite3.connect(
            db_file,
            isolation_level=None,
            detect_types=sqlite3.PARSE_COLNAMES
        )

        self.cursor = self.conn.cursor()

    def list_clients(self) -> List[Tuple[int, str, int]]:
        """
        """
        # self.module.log("ClientManager::list_groups()")

        self.cursor.execute("SELECT id, ip, comment FROM 'client'")

        return self.cursor.fetchall()

    def client_by_ip(self, ip: str) -> Optional[int]:
        self.cursor.execute("SELECT id FROM client WHERE ip = ?", (ip,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def get_group_id(self, name: str) -> Optional[int]:
        self.cursor.execute("SELECT id FROM 'group' WHERE name = ?", (name,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def add_or_update_client(self, ip: str, comment: str = "", groups: List[str] = []):
        client_id = self.client_by_ip(ip)

        if client_id:
            self.cursor.execute("UPDATE client SET comment = ? WHERE id = ?", (comment, client_id))
        else:
            self.cursor.execute(
                "INSERT INTO client (ip, comment) VALUES (?, ?)",
                (ip, comment)
            )
            client_id = self.cursor.lastrowid
            # Trigger übernimmt Gruppenzuweisung zu group_id = 0

        # Gruppen aktualisieren: Trigger deckt initial 0 ab, aber überschreiben wir sauber
        self.cursor.execute("DELETE FROM client_by_group WHERE client_id = ?", (client_id,))
        for group in groups:
            group_id = self.get_group_id(group)
            if group_id is not None:
                self.cursor.execute(
                    "INSERT INTO client_by_group (client_id, group_id) VALUES (?, ?)",
                    (client_id, group_id)
                )
        self.conn.commit()

        return dict(changed=True, msg=f"Client '{ip}' was added or updated.")

    def remove_client(self, ip: str):
        client_id = self.client_by_ip(ip)
        if not client_id:
            return dict(changed=False, msg=f"Client '{ip}' not found.")
        self.cursor.execute("DELETE FROM client WHERE id = ?", (client_id,))
        self.conn.commit()
        return dict(changed=True, msg=f"Client '{ip}' removed.")

    def manage_clients(self, clients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        for c in clients:
            ip = c.get("ip")
            comment = c.get("comment", "")
            groups = c.get("groups", [])
            if not ip:
                continue
            result = self.add_or_update_client(ip, comment, groups)
            results.append({ip: result})
        return results

    def close(self):
        self.conn.close()
