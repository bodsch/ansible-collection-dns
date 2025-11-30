#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2021-2025, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.dns.plugins.module_utils.database import Database

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

        self.state = module.params.get("state")
        self.database = module.params.get("database")
        self.schema_file = module.params.get("schema_file")
        self.owner = module.params.get("owner")
        self.group = module.params.get("group")
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
        result = dict(rc=127, failed=True, changed=False, full_version="unknown")

        result = self._mariadb()

        return result

    def _mariadb(self):
        """
        mysql / mariadb support
        """

        valid, msg = self.validate()

        if not valid:
            return dict(failed=True, msg=msg)

        self.db_credentials(
            self.db_login_username, self.db_login_password, self.db_schemaname
        )

        (db_connect_error, db_message) = self.db_connect()

        if db_connect_error:
            return dict(failed=True, msg=db_message)

        (state, db_error, db_error_message) = self.check_table_schema("domains")

        if state:
            return dict(changed=False, msg=db_error_message)

        # import DB schema
        if os.path.exists(self.schema_file):
            """ """
            # file_name = os.path.basename(self.schema_file)
            # self.module.log(msg=f"import schema from '{file_name}'")

            (state, _msg) = self.import_sqlfile(
                sql_file=self.schema_file,
                commit=True,
                rollback=True,
                close_cursor=False,
            )

            return dict(failed=False, changed=(not state), msg=_msg)


def main():

    arguments = dict(
        state=dict(default="create", choices=["create", "delete"]),
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

    r = PdnsBackendMariadb(module)
    result = r.run()

    # module.log(msg="= result: {}".format(result))

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
