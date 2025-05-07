#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2021-2025, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import os
import sqlite3
import shutil

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


class PdnsBackendMariadb(Database):
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
        self.schemas = module.params.get("schemas")
        self.owner = module.params.get('owner')
        self.group = module.params.get('group')
        self.mode = module.params.get("mode")

        self.db_hostname = self.database.get("hostname", None)
        self.db_port = self.database.get("port", 3306)
        self.db_socket = self.database.get("socket", None)
        self.db_config = self.database.get("config_file", None)
        self.db_schemaname = self.database.get("schemaname", None)
        self.db_login_username = self.database.get("login", {}).get("username", None)
        self.db_login_password = self.database.get("login", {}).get("password", None)

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

        return result


    def _mariadb(self):
        """
            mysql / mariadb support
        """

        valid, msg = self.validate()

        if not valid:
            return dict(
                failed=True,
                msg=msg
            )

        config = self.db_credentials(self.db_login_username, self.db_login_password, self.db_schemaname)

        self.module.log(msg=f"  config: '{self.config}'")


        (db_connect_error, db_message) = self.db_connect()

        self.module.log(msg=f"  '{db_connect_error}' - '{db_message}'")

        if db_connect_error:
            return dict(
                failed=True,
                msg=db_message
            )

        (state, db_error, db_error_message) = self.check_table_schema("domains")

        self.module.log(msg=f"  '{state}' - '{db_error}' - '{db_error_message}'")

        if state:
            return dict(
                changed=False,
                msg=db_error_message
            )

        # import DB schema
        if os.path.exists(self.schemas):
            """
            """
            result_state = {}

            file_name = os.path.basename(self.schemas)
            self.module.log(msg=f"import schema from '{file_name}'")

            (state, _msg) = self.db_import_sqlfile(
                sql_file=self.schemas,
                commit=True,
                rollback=True,
                close_cursor=False
            )

            return dict(
                failed=False,
                changed=(not state),
                msg=_msg
            )




def main():

    arguments = dict(
        state=dict(
            default="create",
            choices=["create", "delete"]
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
        schemas=dict(
            required=True,
            type='str',
        ),
    )

    module = AnsibleModule(
        argument_spec=arguments,
        supports_check_mode=True,
    )

    r = PdnsBackendMariadb(module)
    result = r.run()

    # module.log(msg="= result: {}".format(result))

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
