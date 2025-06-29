#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)
import sqlite3

from typing import List, Dict, Any, Optional
from ansible_collections.bodsch.dns.plugins.module_utils.pihole.database import DataBase


class AdlistManager(DataBase):
    """
    """

    def __init__(self, module: any, database: str):
        """
        """
        self.module = module

        super().__init__(module, database)

    def list_adlists(self):
        self.execute("SELECT id, address, enabled FROM adlist")
        return self.fetchall()

    def adlist_exists(self, address: str) -> bool:
        return self.get_id_by_column("adlist", "address", address) is not None

    def add_adlist(self, address: str, comment: Optional[str] = None, enabled: bool = True) -> Dict[str, Any]:
        if self.adlist_exists(address):
            return dict(changed=False, msg="Adlist already exists.")

        enabled_int = 1 if enabled else 0

        try:
            self.execute(
                "INSERT INTO adlist (address, enabled, comment, date_added) VALUES (?, ?, ?, strftime('%s','now'))",
                (address, enabled_int, comment)
            )
            self.commit()
            return dict(changed=True, msg="Adlist successfully added.")
        except sqlite3.DatabaseError as e:
            self.module.fail_json(msg=f"Failed to insert adlist: {str(e)}")

    def remove_adlist(self, address: str) -> Dict[str, Any]:
        self.execute("DELETE FROM adlist WHERE address = ?", (address,))
        rows_deleted = self.cursor.rowcount
        self.commit()

        if rows_deleted > 0:
            return dict(changed=True, msg="Adlist removed.")
        else:
            return dict(changed=False, msg="Adlist not found.")

    def manage_adlists(self, adlists: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []

        for ad in adlists:
            address = ad.get("address")
            comment = ad.get("comment")
            enabled = ad.get("enabled", True)

            if address and enabled:
                result.append({address: self.add_adlist(address, comment, enabled)})
            elif address and not enabled:
                result.append({address: self.remove_adlist(address)})

        return result

    def sync_adlists(self, desired: List[str]) -> List[Dict[str, Any]]:
        current = [addr for _, addr, _ in self.list_adlists()]
        to_remove = set(current) - set(desired)

        result = []
        for addr in to_remove:
            result.append({addr: self.remove_adlist(addr)})
        return result
