#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2021, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.directory import (
    create_directory,
)
from ansible_collections.bodsch.dns.plugins.module_utils.database import Database

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: pdns_sqlite_backend
short_description: Create, delete or recreate a PowerDNS SQLite backend database and import the schema
version_added: "0.9.0"
author:
  - Bodo Schulz (@bodsch) <bodo@boone-schulz.de>

description:
  - Manages a PowerDNS SQLite backend database file.
  - Ensures the parent directory exists (created with mode C(0750)) before operating on the database.
  - Imports the given SQL schema file when creating the database (implementation provided by the collection database helper).
  - Can delete or recreate the database.

options:
  state:
    description:
      - Desired state of the SQLite backend.
      - C(create) ensures the database exists and schema is present.
      - C(delete) removes the database.
      - C(recreate) deletes and recreates the database.
    type: str
    default: create
    choices: [create, delete, recreate]

  database:
    description:
      - SQLite database definition.
      - The module expects the database file path in C(database.database).
    type: dict
    required: true
    suboptions:
      database:
        description:
          - Path to the SQLite database file.
        type: str
        required: true

  schema_file:
    description:
      - Path to the SQL schema file to import when creating the database.
    type: str
    required: true

  owner:
    description:
      - Owner for the created directory/database (handled by collection helpers).
    type: str
    required: false

  group:
    description:
      - Group for the created directory/database (handled by collection helpers).
    type: str
    required: false

  mode:
    description:
      - File mode for the SQLite database file (octal string, e.g. C(0644)).
    type: str
    default: "0644"
    required: false

notes:
  - Check mode is supported (C(supports_check_mode=true)).
"""

EXAMPLES = r"""
- name: Create PowerDNS SQLite backend and import schema if needed
  become: true
  bodsch.dns.pdns_sqlite_backend:
    state: create
    database:
      database: /var/lib/powerdns/pdns.sqlite3
    schema_file: /usr/share/pdns/schema.sqlite3.sql
    owner: pdns
    group: pdns
    mode: "0640"

- name: Recreate PowerDNS SQLite backend (drop + create)
  become: true
  bodsch.dns.pdns_sqlite_backend:
    state: recreate
    database:
      database: /var/lib/powerdns/pdns.sqlite3
    schema_file: /usr/share/pdns/schema.sqlite3.sql
    owner: pdns
    group: pdns
    mode: "0640"

- name: Delete PowerDNS SQLite backend database file
  become: true
  bodsch.dns.pdns_sqlite_backend:
    state: delete
    database:
      database: /var/lib/powerdns/pdns.sqlite3
    schema_file: /usr/share/pdns/schema.sqlite3.sql
"""

RETURN = r"""
rc:
  description:
    - Return code used by the module implementation.
  returned: always
  type: int
  sample: 0

changed:
  description:
    - Whether the module made changes (e.g. created/imported schema, deleted database, recreated database).
  returned: always
  type: bool

failed:
  description:
    - Indicates failure.
  returned: always
  type: bool

msg:
  description:
    - Human readable status or error message.
  returned: always
  type: str
  sample:
    - "Database successfully created."
    - "Database successfully recreated."
    - "The database has been successfully deleted."
"""

# ---------------------------------------------------------------------------------------


class PdnsBackendSqlite(Database):
    """
    Main Class
    """

    module = None

    def __init__(self, module):
        """
        Initialize all needed Variables
        """
        self.module = module

        self.module.log("PdnsBackendSqlite::__init__()")

        self.state = module.params.get("state")
        self.database = module.params.get("database")
        self.schema_file = module.params.get("schema_file")
        self.owner = module.params.get("owner")
        self.group = module.params.get("group")
        self.mode = module.params.get("mode")

    def run(self):
        """
        runner
        """
        self.module.log("PdnsBackendSqlite::run()")

        result = dict(rc=127, failed=True, changed=False, full_version="unknown")

        res = []

        if isinstance(self.database, list):
            for db in self.database:
                self.module.log(msg=f"  db: '{db}'")

                dbname = db.get("database")
                dirname = os.path.dirname(dbname)

                self.module.log(msg=f"  dirname: '{dirname}'")

                create_directory(
                    directory=dirname, owner=self.owner, group=self.group, mode="0750"
                )

                result = self._sqlite(dbname)

                res.append(result)
        elif isinstance(self.database, dict):
            self.module.log(msg=f"  self.database: '{self.database}'")

            dbname = self.database.get("database")
            dirname = os.path.dirname(dbname)

            self.module.log(msg=f"  dirname: '{dirname}'")

            create_directory(
                directory=dirname, owner=self.owner, group=self.group, mode="0750"
            )

            result = self._sqlite(dbname)

            res.append(result)

        return result

    def _sqlite(self, dbname):
        """ """
        self.module.log(msg=f"PdnsBackendSqlite::_sqlite({dbname})")

        if self.state == "create":
            """ """
            return self.sqlite_create(dbname)

        elif self.state == "delete":
            """ """
            return self.sqlite_remove(dbname)

        elif self.state == "recreate":
            """ """
            self.sqlite_remove(dbname)
            self.sqlite_create(dbname)

            return dict(
                failed=False, changed=True, msg="Database successfully recreated."
            )


def main():

    arguments = dict(
        state=dict(default="create", choices=["create", "delete", "recreate"]),
        database=dict(required=True, type="dict"),
        owner=dict(required=False, type="str"),
        group=dict(required=False, type="str"),
        mode=dict(required=False, type="str", default="0644"),
        schema_file=dict(
            required=True,
            type="str",
        ),
    )

    module = AnsibleModule(
        argument_spec=arguments,
        supports_check_mode=True,
    )

    r = PdnsBackendSqlite(module)
    result = r.run()

    # module.log(msg="= result: {}".format(result))

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
