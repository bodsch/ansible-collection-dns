#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
database.py

Database helper utilities used in an Ansible context.

This module provides a `Database` helper class with two primary responsibilities:

1) SQLite management
   - Create an SQLite database file if it does not exist yet, optionally importing an SQL schema.
   - Remove an SQLite database file.

2) MySQL/MariaDB management (via Ansible mysql_driver abstraction)
   - Validate configuration attributes (hostname, schema, credentials).
   - Build connection credentials, connect, execute queries, import SQL scripts, and
     check for table existence via information_schema.

Integration expectations:
    The class is designed to be used inside Ansible modules. The provided `module` object is
    expected to expose:
        - module.log(msg=...) for debug logging
        - module.fail_json(...) for hard-fail behavior

Important:
    Several instance attributes are expected to be provided externally (e.g. by the calling
    Ansible module) before certain operations are executed:
        - For sqlite_create(): `schema_file`, `owner`, `group`, `mode`
        - For validate()/db_credentials()/db_connect(): `db_hostname`, `db_port`, `db_config`,
          `db_socket`, `db_schemaname`, `db_login_username`, `db_login_password`, etc.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import warnings
from typing import Any, Dict, Optional, Tuple, TypedDict, Union

# from ansible.module_utils._text import to_native
from ansible.module_utils.common.text.converters import to_native
from ansible.module_utils.mysql import mysql_driver, mysql_driver_fail_msg


class AnsibleResult(TypedDict):
    """
    Standard Ansible-style operation result.

    Keys:
        failed: Whether the operation failed.
        changed: Whether the operation changed the system state.
        msg: Human-readable message.
    """

    failed: bool
    changed: bool
    msg: str


DbConnectResult = Tuple[bool, str]
DbValidateResult = Tuple[bool, str]
DbExecuteResult = Tuple[bool, bool, Optional[str]]
ImportSqlResult = Tuple[bool, str]
CheckSchemaResult = Tuple[bool, bool, Optional[str]]


class Database:
    """
    Helper class for SQLite and MySQL/MariaDB operations in an Ansible module context.

    Attributes:
        module: Ansible module-like object providing logging and fail_json.
        config: MySQL/MariaDB connection config dict (populated by `db_credentials()`).
        db_connection: Active DB connection handle (populated by `db_connect()`).
        db_cursor: Active cursor handle (populated by `db_connect()` / refreshed by `db_execute()`).

    Externally provided attributes (expected to be set by the caller as needed):
        schema_file (str): Path to a SQLite schema file imported by `sqlite_create()`.
        owner (str|int|None): Owner for `shutil.chown` in `sqlite_create()`.
        group (str|int|None): Group for `shutil.chown` in `sqlite_create()`.
        mode (str|int): File mode applied in `sqlite_create()`.

        db_config (str|None): MySQL default file for credentials (optional).
        db_socket (str|None): MySQL unix socket (optional).
        db_hostname (str|None): MySQL host.
        db_port (int): MySQL port.
        db_schemaname (str|None): DB schema name.
        db_login_username (str|None): Login username.
        db_login_password (str|None): Login password.
    """

    def __init__(self, module: Any) -> None:
        """
        Initialize the Database helper.

        Args:
            module: Ansible module-like object.

        Returns:
            None
        """
        self.module = module
        self.module.log("Database::__init__(module)")

        # MySQL runtime state (set during operation)
        self.config: Dict[str, Any] = {}
        self.db_connection: Any = None
        self.db_cursor: Any = None

        # Optional externally populated defaults / settings
        self.schema_file: str = ""
        self.owner: Optional[Union[str, int]] = None
        self.group: Optional[Union[str, int]] = None
        self.mode: Union[str, int] = "0600"

        self.db_config: Optional[str] = None
        self.db_socket: Optional[str] = None
        self.db_hostname: Optional[str] = None
        self.db_port: int = 3306
        self.db_schemaname: Optional[str] = None
        self.db_login_username: Optional[str] = None
        self.db_login_password: Optional[str] = None

    def sqlite_create(self, database_file: str) -> AnsibleResult:
        """
        Create (or initialize) an SQLite database file.

        Behavior:
            - Opens (or creates) the SQLite DB file.
            - Checks whether non-metadata tables exist.
            - If no tables exist, imports SQL schema from `self.schema_file`.
            - Sets ownership (`shutil.chown`) and file mode (`os.chmod`) after creation.

        Preconditions:
            - `self.schema_file` must point to a readable SQL schema file if initialization is needed.
            - `self.owner`, `self.group`, and `self.mode` should be configured if ownership/mode
              should be enforced.

        Args:
            database_file: Path to the SQLite database file.

        Returns:
            AnsibleResult:
                failed: True if an SQLite error occurred, else False.
                changed: True if schema was imported (fresh DB), else False.
                msg: Status message describing the outcome.
        """
        self.module.log(f"Database::sqlite_create({database_file})")

        failed = False
        changed = False
        msg = ""

        conn: Optional[sqlite3.Connection] = None

        try:
            conn = sqlite3.connect(
                database_file, isolation_level=None, detect_types=sqlite3.PARSE_COLNAMES
            )
            conn.row_factory = lambda cursor, row: row[0]

            self.module.log(f"SQLite Version: '{sqlite3.sqlite_version}'")

            query = "SELECT name FROM sqlite_schema WHERE type ='table' AND name not LIKE '%metadata%'"
            cursor = conn.execute(query)
            schemas = cursor.fetchall()
            self.module.log(f"  - schemas '{schemas}")

            if len(schemas) == 0:
                # Import SQL schema
                self.module.log(msg="import database schemas")

                with open(self.schema_file, "r", encoding="utf-8") as f:
                    cursor.executescript(f.read())

                changed = True
                msg = "Database successfully created."
            else:
                msg = "Database already exists."

            # Apply ownership/mode (caller must ensure values are correct and process has permissions)
            shutil.chown(database_file, self.owner, self.group)

            mode: int
            if isinstance(self.mode, str):
                mode = int(self.mode, base=8)
            else:
                mode = int(self.mode)

            os.chmod(database_file, mode)

        except sqlite3.Error as er:
            self.module.log(f"SQLite error: '{(' '.join(er.args))}'")
            self.module.log(f"Exception class is '{er.__class__}'")

            failed = True
            msg = " ".join(er.args)

        finally:
            if conn:
                conn.close()

        return {"failed": failed, "changed": changed, "msg": msg}

    def sqlite_remove(self, database_file: str) -> AnsibleResult:
        """
        Remove an SQLite database file if it exists.

        Args:
            database_file: Path to the SQLite database file.

        Returns:
            AnsibleResult:
                failed: Always False in the current implementation (filesystem errors would raise).
                changed: True if the file existed and was removed, else False.
                msg: Status message describing the outcome.
        """
        self.module.log(f"Database::sqlite_remove({database_file})")

        failed = False
        changed = False

        if os.path.exists(database_file):
            os.remove(database_file)
            changed = True
            msg = "The database has been successfully deleted."
        else:
            msg = f"The database file '{database_file}' does not exist."

        return {"failed": failed, "changed": changed, "msg": msg}

    def validate(self) -> DbValidateResult:
        """
        Validate MySQL/MariaDB database configuration attributes on this instance.

        Validates that the following instance attributes are configured:
            - db_hostname
            - db_schemaname
            - db_login_username
            - db_login_password

        Returns:
            tuple[bool, str]: (ok, message)
                ok: True if all required attributes are present, else False.
                message: Empty string on success, otherwise an "ERROR: ..." message with details.
        """
        msg = ""
        errors = []
        result = False

        if not self.db_hostname:
            errors.append("`database.hostname` was not configured.")
        if not self.db_schemaname:
            errors.append("`database.schemaname` was not configured.")
        if not self.db_login_username:
            errors.append("`database.login.username` was not configured.")
        if not self.db_login_password:
            errors.append("`database.login.password` was not configured.")

        if len(errors) > 0:
            _msg = ", ".join(errors)
            msg = f"ERROR: {_msg}"
        else:
            result = True

        return (result, msg)

    def db_credentials(
        self,
        db_username: Optional[str],
        db_password: Optional[str],
        db_schema_name: str,
    ) -> None:
        """
        Build and store MySQL/MariaDB connection credentials in `self.config`.

        Behavior:
            - Reads credentials from `self.db_config` if configured and file exists.
            - Uses unix socket if `self.db_socket` is set; otherwise uses host/port.
            - Explicit `db_username` / `db_password` override config file credentials.

        Args:
            db_username: Username to authenticate with (overrides config file).
            db_password: Password to authenticate with (overrides config file).
            db_schema_name: Target database schema name.

        Returns:
            None
        """
        config: Dict[str, Any] = {}

        if self.db_config and os.path.exists(self.db_config):
            config["read_default_file"] = self.db_config

        if self.db_socket:
            config["unix_socket"] = self.db_socket
        else:
            config["host"] = self.db_hostname
            config["port"] = self.db_port

        if db_username is not None:
            config["user"] = db_username
        if db_password is not None:
            config["passwd"] = db_password

        config["db"] = db_schema_name

        self.config = config

    def db_connect(self) -> DbConnectResult:
        """
        Connect to MySQL/MariaDB using `self.config`.

        Behavior:
            - Ensures the Ansible mysql_driver is available; otherwise fails the module.
            - Treats mysql_driver warnings as errors (`warnings.filterwarnings`).
            - Creates `self.db_connection` and `self.db_cursor`.

        Returns:
            tuple[bool, str]: (db_connect_error, message)
                db_connect_error: False on success, True on failure.
                message: A human-readable status message.
        """
        if mysql_driver is None:
            self.module.fail_json(msg=mysql_driver_fail_msg)
        else:
            warnings.filterwarnings("error", category=mysql_driver.Warning)

        db_connect_error = True

        try:
            self.db_connection = mysql_driver.connect(**self.config)
            self.db_cursor = self.db_connection.cursor()
            db_connect_error = False

        except mysql_driver.Warning as e:
            message = "unable to connect to database. "
            message += f"Exception message: {to_native(e)}"

            self.module.log(msg=message)
            return (db_connect_error, message)

        except Exception as e:
            message = "unable to connect to database. "
            message += "check login_host, login_user and login_password are correct "
            message += f"or {self.db_config} has the credentials. "
            message += f"Exception message: {to_native(e)}"

            self.module.log(msg=message)
            return (db_connect_error, message)

        return (db_connect_error, "successful connected")

    def db_execute(
        self,
        query: str,
        commit: bool = True,
        rollback: bool = True,
        close_cursor: bool = False,
    ) -> DbExecuteResult:
        """
        Execute a single SQL query against an established MySQL/MariaDB connection.

        Behavior:
            - If the query does not start with "--", it is executed.
            - Commits on success if `commit=True`.
            - On exceptions, optionally rolls back if `rollback=True`.
            - Optionally closes the cursor if `close_cursor=True`.

        Args:
            query: SQL statement to execute.
            commit: Whether to commit after executing the query.
            rollback: Whether to roll back the current transaction on unexpected errors.
            close_cursor: Whether to close the cursor before returning.

        Returns:
            tuple[bool, bool, Optional[str]]: (state, db_error, db_message)
                state: True if the query execution path completed (including no-op comment queries),
                       False if it did not execute successfully.
                db_error: True if an unexpected exception occurred, else False.
                db_message: Error message if `db_error=True`, otherwise None.
        """
        if self.db_connection:
            self.db_cursor = self.db_connection.cursor()

        state = False
        db_error = False
        db_message: Optional[str] = None

        try:
            if not query.startswith("--"):
                self.db_cursor.execute(query)
                if commit:
                    self.db_connection.commit()
            state = True

        except mysql_driver.Warning as e:
            try:
                error_id = e.args[0]
                error_msg = e.args[1]
                self.module.log(f"WARNING: {error_id} - {error_msg}")
            except Exception:
                self.module.log(f"WARNING: {str(e)}")

        except mysql_driver.Error as e:
            try:
                error_id = e.args[0]
                error_msg = e.args[1]

                if error_id == 1050:  # Table '...' already exists
                    self.module.log(f"WARNING: {error_msg}")
            except Exception:
                self.module.log(f"ERROR: {str(e)}")

        except Exception as e:
            db_error = True
            db_message = f"Cannot execute SQL '{query}' : {to_native(e)}"

            if rollback:
                self.db_connection.rollback()

        finally:
            if close_cursor and self.db_cursor:
                self.db_cursor.close()

        return (state, db_error, db_message)

    def import_sqlfile(
        self,
        sql_file: str,
        commit: bool = True,
        rollback: bool = True,
        close_cursor: bool = False,
    ) -> ImportSqlResult:
        """
        Import a full SQL script file into the connected MySQL/MariaDB database.

        Implementation details:
            - The file content is split by ";\n" to get statements.
            - Lines starting with "--" (SQL comments) are ignored.
            - Statements are executed sequentially via `db_execute()`.
            - On error, processing stops and (optionally) a rollback is performed.

        Args:
            sql_file: Path to the SQL script file.
            commit: Whether to commit after processing all statements successfully.
            rollback: Whether to roll back if any statement fails.
            close_cursor: Whether to close the cursor before returning.

        Returns:
            tuple[bool, str]: (state, message)
                state: False if file does not exist; otherwise True after processing.
                       Note: On SQL failure, `state` is set to True in the original logic.
                message: Human-readable success or error message.
        """
        self.module.log(
            f"Database::import_sqlfile(sql_file={sql_file}, commit={commit}, rollback={rollback}, close_cursor={close_cursor})"
        )

        if not os.path.exists(sql_file):
            return (False, f"The file {sql_file} does not exist.")

        state = False
        db_error = False
        db_message: Optional[str] = None
        msg: str

        with open(sql_file, encoding="utf8") as f:
            sql_data = f.read()
            sql_commands = sql_data.split(";\n")
            sql_commands = [
                x.replace("\n", "").strip()
                for x in sql_commands
                if not x.replace("\n", "").strip().startswith("--")
            ]

            for command in sql_commands:
                state = False
                db_error = False
                db_message = None

                if command:
                    (state, db_error, db_message) = self.db_execute(
                        query=command, commit=commit
                    )
                    if db_error:
                        break

            if rollback and db_error:
                self.db_connection.rollback()

            if commit and not db_error:
                self.db_connection.commit()

            if close_cursor and self.db_cursor:
                self.db_cursor.close()

        if db_error:
            state = True
            msg = f"Cannot import file '{sql_file}' : {to_native(db_message)}"
        else:
            file_name = os.path.basename(sql_file)
            msg = f"file '{file_name}' successful imported."

        return (state, msg)

    def check_table_schema(self, database_table_name: str) -> CheckSchemaResult:
        """
        Check whether a database table exists using `information_schema.tables`.

        Args:
            database_table_name: Table name to verify.

        Returns:
            tuple[bool, bool, Optional[str]]: (state, db_error, db_error_message)
                state: True if exactly one row was found (table exists), else False.
                db_error: Always False in the current implementation (errors are logged only).
                db_error_message: Message describing the result; empty/None if not found or on error.

        Notes:
            - The query uses string formatting; if `database_table_name` is user-controlled,
              parameterize it to avoid SQL injection. In Ansible-controlled inputs this may be acceptable
              but still not ideal.
        """
        state = False
        db_error = False
        db_error_message: Optional[str] = ""

        q = f"SELECT * FROM information_schema.tables WHERE table_name = '{database_table_name}'"

        number_of_rows = 0

        try:
            number_of_rows = self.db_cursor.execute(q)
            self.db_cursor.fetchone()

        except mysql_driver.Warning as e:
            try:
                error_id = e.args[0]
                error_msg = e.args[1]
                self.module.log(f"WARNING: {error_id} - {error_msg}")
            except Exception:
                self.module.log(f"WARNING: {str(e)}")

        except mysql_driver.Error as e:
            try:
                error_id = e.args[0]
                error_msg = e.args[1]

                if (
                    error_id == 1050
                ):  # Table '...' already exists (not typical for SELECT)
                    self.module.log(f"WARNING: {error_msg}")
            except Exception:
                self.module.log(f"ERROR: {str(e)}")

        except Exception as e:
            self.module.log(f"Cannot execute SQL '{q}' : {to_native(e)}")

        if number_of_rows == 1:
            state = True
            db_error = False
            db_error_message = (
                f"The database schema '{database_table_name}' has already been created."
            )

        return (state, db_error, db_error_message)
