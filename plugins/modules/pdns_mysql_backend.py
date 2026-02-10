#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2021-2025, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.dns.plugins.module_utils.database import Database

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: pdns_mysql_backend
short_description: Ensure a PowerDNS MariaDB/MySQL backend schema is present (import schema if missing)
version_added: "0.9.0"
author:
  - Bodo Schulz (@bodsch) <bodo@boone-schulz.de>

description:
  - Connects to a MariaDB/MySQL server and verifies the PowerDNS schema by checking for the C(domains) table.
  - If the schema is missing, imports the given SQL schema file.
  - Intended to bootstrap the PowerDNS gmysql backend schema.
  - Note: While C(state=delete) is accepted by the argument spec, this module implementation only performs schema validation/import.

options:
  state:
    description:
      - Desired state.
      - C(create) validates the schema and imports it if missing.
      - C(delete) is currently not implemented for MariaDB/MySQL by this module code path.
    type: str
    default: create
    choices: [create, delete]

  database:
    description:
      - Database connection parameters for MariaDB/MySQL.
    type: dict
    required: true
    suboptions:
      hostname:
        description:
          - Database hostname or IP.
        type: str
        required: false
      port:
        description:
          - Database port.
        type: int
        required: false
        default: 3306
      socket:
        description:
          - Path to the UNIX socket (optional, alternative to hostname/port).
        type: str
        required: false
      config_file:
        description:
          - Optional client config file used by the underlying database helper.
        type: str
        required: false
      schemaname:
        description:
          - Database/schema name to connect to.
        type: str
        required: false
      login:
        description:
          - Login credentials.
        type: dict
        required: false
        suboptions:
          username:
            description:
              - Login user.
            type: str
            required: false
          password:
            description:
              - Login password.
            type: str
            required: false
            no_log: true

  schema_file:
    description:
      - Path to the SQL schema file to import if the PowerDNS schema is missing.
    type: str
    required: true

  owner:
    description:
      - Optional compatibility parameter (not used directly by this module code path).
    type: str
    required: false

  group:
    description:
      - Optional compatibility parameter (not used directly by this module code path).
    type: str
    required: false

  mode:
    description:
      - Optional compatibility parameter (not used directly by this module code path).
    type: str
    default: "0644"
    required: false

notes:
  - Check mode is supported.

requirements:
  - MariaDB/MySQL connectivity as provided by the collection's C(Database) helper utilities.
"""

EXAMPLES = r"""
- name: Ensure PowerDNS schema exists in MariaDB and import if missing
  become: true
  bodsch.dns.pdns_mysql_backend:
    state: create
    database:
      hostname: 127.0.0.1
      port: 3306
      schemaname: powerdns
      login:
        username: pdns
        password: secret
    schema_file: /usr/share/pdns/schema.mysql.sql

- name: Use a UNIX socket and a client config file
  become: true
  bodsch.dns.pdns_mysql_backend:
    state: create
    database:
      socket: /run/mysqld/mysqld.sock
      config_file: /root/.my.cnf
      schemaname: powerdns
    schema_file: /usr/share/pdns/schema.mysql.sql
"""

RETURN = r"""
changed:
  description:
    - Whether the module imported the schema.
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
    - "schema already present"
    - "imported schema successfully"
    - "connection failed: <details>"

rc:
  description:
    - Return code used by the module implementation (may be absent depending on the executed code path).
  returned: sometimes
  type: int
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

        db_connect_error, db_message = self.db_connect()

        if db_connect_error:
            return dict(failed=True, msg=db_message)

        state, db_error, db_error_message = self.check_table_schema("domains")

        if state:
            return dict(changed=False, msg=db_error_message)

        # import DB schema
        if os.path.exists(self.schema_file):
            """ """
            # file_name = os.path.basename(self.schema_file)
            # self.module.log(msg=f"import schema from '{file_name}'")

            state, _msg = self.import_sqlfile(
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
