#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2021-2025, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, division, print_function

import os
import sqlite3
import shutil

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.dns.plugins.module_utils.database import Database
# from ansible_collections.bodsch.core.plugins.module_utils.directory import create_directory

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


class PdnsDatabaseBackend(Database):
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
        self.db_type = module.params.get("type")
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

        if self.db_type == "sqlite3":
            result = self._sqlite(None)

        if self.db_type == "mariadb":
            result = self._mariadb()

        return result

    def _sqlite(self, dbname):
        """
        """
        self.module.log(msg=f"_sqlite({dbname})")

        database_file = dbname

        _failed = False
        _changed = False
        _msg = ""

        if self.state == "create":
            """
            """
            conn = None

            try:
                conn = sqlite3.connect(
                    database_file,
                    isolation_level=None,
                    detect_types=sqlite3.PARSE_COLNAMES
                )
                conn.row_factory = lambda cursor, row: row[0]

                self.module.log(msg=f"SQLite Version: '{sqlite3.version}'")

                query = "SELECT name FROM sqlite_schema WHERE type ='table' AND name not LIKE '%metadata%'"
                cursor = conn.execute(query)
                schemas = cursor.fetchall()
                self.module.log(msg=f"  - schemas '{schemas}")

                if len(schemas) == 0:
                    """
                      import sql schema
                    """
                    self.module.log(msg="import database schemas")

                    with open(self.schemas, 'r') as f:
                        cursor.executescript(f.read())

                    _changed = True
                    _msg = "Database successfully created."
                else:
                    _msg = "Database already exists."

                shutil.chown(database_file, self.owner, self.group)
                if isinstance(self.mode, str):
                    mode = int(self.mode, base=8)

                os.chmod(database_file, mode)

            except sqlite3.Error as er:
                self.module.log(msg=f"SQLite error: '{(' '.join(er.args))}'")
                self.module.log(msg=f"Exception class is '{er.__class__}'")

                _failed = True
                _msg = (' '.join(er.args))

            # exception sqlite3.Warning
            # # A subclass of Exception.
            #
            # exception sqlite3.Error
            # # The base class of the other exceptions in this module. It is a subclass of Exception.
            #
            # exception sqlite3.DatabaseError
            # # Exception raised for errors that are related to the database.
            #
            # exception sqlite3.IntegrityError
            # # Exception raised when the relational integrity of the database is affected, e.g. a foreign key check fails.
            # It is a subclass of DatabaseError.
            #
            # exception sqlite3.ProgrammingError
            # # Exception raised for programming errors, e.g. table not found or already exists, syntax error in the SQL statement,
            # wrong number of parameters specified, etc. It is a subclass of DatabaseError.
            #
            # exception sqlite3.OperationalError
            # # Exception raised for errors that are related to the database’s operation and not necessarily under the control of the programmer,
            # e.g. an unexpected disconnect occurs, the data source name is not found, a transaction could not be processed, etc.
            # It is a subclass of DatabaseError.
            #
            # exception sqlite3.NotSupportedError
            # # Exception raised in case a method or database API was used which is not supported by the database,
            # e.g. calling the rollback() method on a connection that does not support transaction or has transactions turned off.
            # It is a subclass of DatabaseError.

            finally:
                if conn:
                    conn.close()

            return dict(
                rc=0,
                failed=_failed,
                changed=_changed,
                msg=_msg
            )

        elif self.state == "delete":
            """
            """
            if isinstance(self.databases, list):
                for db in self.databases:
                    dbname = db.get("database")

                    if os.path.exists(dbname):
                        os.remove(dbname)
                        _changed = True
                        _msg = "The database has been successfully deleted."
                    else:
                        _msg = f"The database file '{dbname}' does not exist."

            return dict(
                rc=0,
                failed=_failed,
                changed=_changed,
                msg=_msg
            )

        return []

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

        self.config = self.db_credentials(self.db_login_username, self.db_login_password, self.db_schemaname)

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
            # result_state = {}

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
        type=dict(
            default="sqlite3",
            choices=["sqlite3", "mariadb"]
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

    r = PdnsDatabaseBackend(module)
    result = r.run()

    # module.log(msg="= result: {}".format(result))

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
