#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2021, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.dns.plugins.module_utils.database import Database
from ansible_collections.bodsch.core.plugins.module_utils.directory import create_directory

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
module: pdns_version
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: return the version of installed pdns
description: return the version of installed pdns

options:
  validate_version:
    description: check against the installed version.
    type: str
    required: false

"""

EXAMPLES = r"""
- name: detect pdns version
  become: true
  bodsch.dns.pdns_version:
  register: pdns_version
  check_mode: false
  ignore_errors: true

- name: detect pdns version
  become: true
  bodsch.dns.pdns_version:
    validate_version: '9.18.0'
  register: pdns_version
  check_mode: false
  ignore_errors: true
"""

RETURN = """
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

        self.state = module.params.get('state')
        self.database = module.params.get("database")
        self.schema_file = module.params.get("schema_file")
        self.owner = module.params.get('owner')
        self.group = module.params.get('group')
        self.mode = module.params.get("mode")

    def run(self):
        """
          runner
        """
        result = dict(
            rc=127,
            failed=True,
            changed=False,
            full_version="unknown"
        )

        res = []

        if isinstance(self.database, list):
            for db in self.database:
                self.module.log(msg=f"  db: '{db}'")

                dbname = db.get("database")
                dirname = os.path.dirname(dbname)

                self.module.log(msg=f"  dirname: '{dirname}'")

                create_directory(directory=dirname, owner=self.owner, group=self.group, mode="0750")

                result = self._sqlite(dbname)

                res.append(result)
        elif isinstance(self.database, dict):
            self.module.log(msg=f"  self.database: '{self.database}'")

            dbname = self.database.get("database")
            dirname = os.path.dirname(dbname)

            self.module.log(msg=f"  dirname: '{dirname}'")

            create_directory(directory=dirname, owner=self.owner, group=self.group, mode="0750")

            result = self._sqlite(dbname)

            res.append(result)

        return result

    def _sqlite(self, dbname):
        """
        """
        self.module.log(msg=f"_sqlite({dbname})")

        if self.state == "create":
            """
            """
            return self.sqlite_create(dbname)

        elif self.state == "delete":
            """
            """
            return self.sqlite_remove(dbname)

        elif self.state == "recreate":
            """
            """
            self.sqlite_remove(dbname)
            self.sqlite_create(dbname)

            return dict(
                failed=False,
                changed=True,
                msg="Database successfully recreated."
            )


def main():

    arguments = dict(
        state=dict(
            default="create",
            choices=["create", "delete", "recreate"]
        ),
        database=dict(
            required=True,
            type='dict'
        ),
        owner=dict(
            required=False,
            type='str'
        ),
        group=dict(
            required=False,
            type='str'
        ),
        mode=dict(
            required=False,
            type='str',
            default="0644"
        ),
        schema_file=dict(
            required=True,
            type='str',
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
if __name__ == '__main__':
    main()
