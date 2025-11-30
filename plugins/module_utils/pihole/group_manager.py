#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from ansible_collections.bodsch.dns.plugins.module_utils.pihole.database import DataBase


class GroupManager(DataBase):
    """ """

    def __init__(self, module: any, database: str):
        """ """
        self.module = module

        # self.module.log(f"GroupManager::__init__(module, database={database})")

        super().__init__(module, database)

    def list_groups(self) -> List[Tuple[int, str, int]]:
        """ """
        # self.module.log("GroupManager::list_groups()")

        self.execute("SELECT id, name, enabled FROM 'group'")
        return self.fetchall()

    def group_exists(self, name: str) -> bool:
        """ """
        # self.module.log(f"GroupManager::group_exists(name={name})")
        return self.get_id_by_column("group", "name", name) is not None

    def add_group(
        self, name: str, description: Optional[str] = None, enabled: bool = True
    ):
        """ """
        # self.module.log(f"GroupManager::add_group(name={name}, description={description}, enabled={enabled})")
        if self.group_exists(name):
            return dict(changed=False, msg="Group already created.")

        enabled_int = 1 if enabled else 0

        try:
            self.execute(
                "INSERT INTO 'group' (enabled, name, description, date_added) VALUES (?, ?, ?, strftime('%s','now'))",
                (enabled_int, name, description),
            )
            self.commit()
            return dict(changed=True, msg="Group successfully created.")
        except sqlite3.DatabaseError as e:
            return dict(
                failed=True,
                changed=False,
                msg=f"Failed to insert group '{name}': {str(e)}",
            )

    def remove_group(self, name: str) -> Dict[str, Any]:
        """ """
        # self.module.log(f"GroupManager::remove_group(name={name})")
        try:
            self.execute("DELETE FROM 'group' WHERE name = ?", (name,))
            rows_deleted = self.cursor.rowcount
            self.commit()

            if rows_deleted > 0:
                return dict(changed=True, msg="Group removed.")
            else:
                return dict(changed=False, msg="Group not found.")
        except sqlite3.DatabaseError as e:
            self.module.fail_json(msg=f"Failed to remove group: {str(e)}")

    def manage_groups(
        self, groups: List[Dict[str, Any]]
    ) -> List[Dict[str, Dict[str, Any]]]:
        """ """
        # self.module.log(f"GroupManager::manage_groups(groups={groups})")
        result = []
        for g in groups:
            name = g.get("name")
            description = g.get("description")
            enabled = g.get("enabled", True)

            if name and enabled:
                result.append({name: self.add_group(name, description, enabled)})
            elif name and not enabled:
                result.append({name: self.remove_group(name)})

        return result
