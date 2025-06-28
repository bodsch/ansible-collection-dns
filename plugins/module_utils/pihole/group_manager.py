#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)
import sqlite3

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


class GroupManager():
    """
    """

    def __init__(self, module: any, database: str):
        """
        """
        self.module = module

        # self.module.log(f"GroupManager::__init__(module, database={database})")

        db_file = Path(database)

        if not db_file.exists():
            raise FileNotFoundError(f"Pi-hole DB not found at: {db_file}")

        self.conn = sqlite3.connect(
            db_file,
            isolation_level=None,
            detect_types=sqlite3.PARSE_COLNAMES
        )

        self.cursor = self.conn.cursor()

    def list_groups(self) -> List[Tuple[int, str, int]]:
        """
        """
        # self.module.log("GroupManager::list_groups()")

        self.cursor.execute("SELECT id, name, enabled FROM 'group'")

        return self.cursor.fetchall()

    def group_exists(self, name: str) -> bool:
        """
        """
        # self.module.log(f"GroupManager::group_exists(name={name})")

        self.cursor.execute("SELECT id FROM 'group' WHERE name = ?", (name,))
        return self.cursor.fetchone() is not None

    def add_group(self, name: str, description: Optional[str] = None, enabled: bool = True):
        """
        """
        # self.module.log(f"GroupManager::add_group(name={name}, description={description}, enabled={enabled})")

        if self.group_exists(name):
            return dict(
                changed=False,
                msg="Group already created."
            )

        enabled_int = 1 if enabled else 0

        try:
            self.cursor.execute(
                "INSERT INTO 'group' (enabled, name, description, date_added) VALUES (?, ?, ?, strftime('%s','now'))",
                (enabled_int, name, description)
            )
            self.conn.commit()

        except sqlite3.DatabaseError as e:
            return dict(
                failed=True,
                changed=False,
                msg=f"Failed to insert group '{name}': {str(e)}"
            )

        return dict(
            changed=True,
            msg="Group successfuly created."
        )

    def remove_group(self, name: str) -> Dict[str, Any]:
        """
        """
        # self.module.log(f"GroupManager::remove_group(name={name})")
        try:
            self.cursor.execute("DELETE FROM 'group' WHERE name = ?", (name,))
            rows_deleted = self.cursor.rowcount
            self.conn.commit()

            self.module.log(f"Rows deleted: {rows_deleted}")

            if rows_deleted > 0:
                return dict(changed=True, msg="Group removed.")
            else:
                return dict(changed=False, msg="Group did not exist (case mismatch or already removed).")

        except sqlite3.DatabaseError as e:
            self.module.fail_json(msg=f"Failed to remove adlist: {str(e)}")

    def manage_groups(self, groups: List[Dict[str, Any]]) -> List[Dict[str, Dict[str, Any]]]:
        """
        """
        # self.module.log(f"GroupManager::manage_groups(groups={groups})")
        result_state = []

        for group in groups:
            res = {}
            name = group.get("name")
            description = group.get("description", None)
            enabled = group.get("enabled", True)

            if name and enabled:
                res[name] = self.add_group(name=name, description=description, enabled=enabled)
            elif name and not enabled:
                res[name] = self.remove_group(name=name)

            result_state.append(res)

        return result_state

    def close(self):
        """
        """
        # self.module.log("GroupManager::close()")
        self.conn.close()
