#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)
import sqlite3

from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse


class PiholeAdlistManager():
    """
    """

    def __init__(self, module: any, database: str):
        """
        """
        self.module = module

        self.module.log("PiholeAdlistManager::__init__()")

        db_file = Path(database)

        if not db_file.exists():
            raise FileNotFoundError(f"Pi-hole DB not found at: {db_file}")

        self.conn = sqlite3.connect(
            db_file,
            isolation_level=None,
            detect_types=sqlite3.PARSE_COLNAMES
        )

        self.cursor = self.conn.cursor()

    def list_adlists(self):
        self.module.log("PiholeAdlistManager::list_adlists()")
        self.cursor.execute("SELECT id, address, enabled FROM adlist")
        return self.cursor.fetchall()

    def adlist_exists(self, address: str) -> bool:
        self.module.log(f"PiholeAdlistManager::adlist_exists(address={address})")
        self.cursor.execute("SELECT id FROM adlist WHERE address = ?", (address,))
        return self.cursor.fetchone() is not None

    def add_adlist(self, address: str, comment: Optional[str] = None, enabled: bool = True):
        self.module.log(f"PiholeAdlistManager::add_adlist(address={address}, comment={comment}, enabled={enabled})")

        if self.adlist_exists(address):
            return dict(
                changed=False,
                msg="Adlist already exists."
            )

        enabled_int = 1 if enabled else 0

        try:
            self.cursor.execute(
                "INSERT INTO adlist (address, enabled, comment, date_added) VALUES (?, ?, ?, strftime('%s','now'))",
                (address, enabled_int, comment)
            )
            self.conn.commit()
            return dict(changed=True, msg="Adlist successfully added.")
        except sqlite3.DatabaseError as e:
            self.module.fail_json(msg=f"Failed to insert adlist: {str(e)}")

    def manage_adlists(self, adlists: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.module.log(f"PiholeAdlistManager::manage_adlists(adlists={adlists})")
        result_state = []

        sanitized = self.sanitize_adlist_config(adlists)

        for ad in sanitized:
            address = ad.get("address")
            comment = ad.get("comment", None)
            enabled = ad.get("enabled", True)

            if address and enabled:
                res = self.add_adlist(address=address, comment=comment, enabled=enabled)
            elif address and not enabled:
                res = self.remove_adlist(address=address)

            result_state.append({address: res})

        return result_state

    def remove_adlist(self, address: str):
        self.module.log(f"PiholeAdlistManager::remove_adlist(address={address})")

        try:
            self.cursor.execute("DELETE FROM adlist WHERE address = ?", (address,))
            rows_deleted = self.cursor.rowcount
            self.conn.commit()

            self.module.log(f"Rows deleted: {rows_deleted}")

            if rows_deleted > 0:
                return dict(changed=True, msg="Adlist removed.")
            else:
                return dict(changed=False, msg="Adlist did not exist (case mismatch or already removed).")

        except sqlite3.DatabaseError as e:
            self.module.fail_json(msg=f"Failed to remove adlist: {str(e)}")

    def sync_adlists(self, desired: List[str]) -> List[Dict[str, Any]]:
        """
        Remove adlists not in the desired list
        """
        self.module.log(f"PiholeAdlistManager::sync_adlists(desired={desired})")
        current = [addr for _, addr, _ in self.list_adlists()]
        to_remove = set(current) - set(desired)

        result_state = []
        for addr in to_remove:
            res = self.remove_adlist(addr)
            result_state.append({addr: res})

        return result_state

    def close(self):
        self.module.log("PiholeAdlistManager::close()")
        self.conn.close()

    def sanitize_adlist_config(self, adlists: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        cleaned = []

        for ad in adlists:
            address = ad.get("address")
            if not address:
                continue

            # normalize (e.g., strip whitespaces, lowercase if needed)
            address = address.strip()

            # validate URL
            parsed = urlparse(address)
            if not parsed.scheme.startswith("http"):
                continue  # skip invalid

            if address in seen:
                continue  # skip duplicates

            seen.add(address)

            cleaned.append(dict(
                address=address,
                comment=ad.get("comment", ""),
                enabled=ad.get("enabled", True)
            ))

        return cleaned
