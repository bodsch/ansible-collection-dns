#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)

import os

from ansible.module_utils._text import to_native
from ansible.module_utils.mysql import (
    mysql_driver
)

class Database():

    def __init__(self, module):
        """
        """
        self.module = module


    def sqlite(self):
        """
        """



    def validate(self):
        """
            validate mysql/mariad database informations
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
            _msg =", ".join(errors)
            msg = f"ERROR: {_msg}"
        else:
            result = True

        return (result, msg)

    def db_credentials(self, db_username, db_password, db_schema_name):
        """
        """
        # self.module.log(f"Database::db_credentials({db_username}, {db_password}, {db_schema_name})")

        config = {}

        if self.db_config and os.path.exists(self.db_config):
            config['read_default_file'] = self.db_config

        if self.db_socket:
            config['unix_socket'] = self.db_socket
        else:
            config['host'] = self.db_hostname
            config['port'] = self.db_port

        # If login_user or login_password are given, they should override the
        # config file
        if db_username is not None:
            config['user'] = db_username
        if db_password is not None:
            config['passwd'] = db_password

        config['db'] = db_schema_name

        self.config = config

    def db_connect(self):
        """
            connect to Database
        """
        # self.module.log(f"Database::db_connect()")

        db_connect_error = True

        try:
            self.db_connection = mysql_driver.connect(**self.config)
            self.db_cursor = self.db_connection.cursor()
            db_connect_error = False

        except Exception as e:
            message = "unable to connect to database. "
            message += "check login_host, login_user and login_password are correct "
            message += f"or {self.db_config} has the credentials. "
            message += f"Exception message: {to_native(e)}"

            self.module.log(msg=message)
            return (db_connect_error, message)

        return (db_connect_error, "successful connected")

    def db_execute(self, query, commit=True, rollback=True, close_cursor=False):
        """
            execute Query
        """
        # self.module.log(f"Database::db_execute(query={query}, commit={commit}, rollback={rollback}, close_cursor={close_cursor})")

        # if not self.db_cursor:
        if self.db_connection:
            self.db_cursor = self.db_connection.cursor()

        state = False
        db_error = False
        db_message = None

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
                self.module.log(msg=f"WARNING: {error_id} - {error_msg}")
                pass
            except Exception:
                self.module.log(msg=f"WARNING: {str(e)}")
                pass

        except mysql_driver.Error as e:
            try:
                error_id = e.args[0]
                error_msg = e.args[1]

                if error_id == 1050:  # Table '...' already exists
                    self.module.log(msg=f"WARNING: {error_msg}")
                    pass
            except Exception:
                self.module.log(msg=f"ERROR: {str(e)}")
                pass

        except Exception as e:
            db_error = True
            db_message = f"Cannot execute SQL '{query}' : {to_native(e)}"

            if rollback:
                self.db_connection.rollback()

            pass

        finally:
            if close_cursor:
                self.db_cursor.close()

        return (state, db_error, db_message)

    def db_import_sqlfile(self, sql_file, commit=True, rollback=True, close_cursor=False):
        """
            import complete SQL script
        """
        self.module.log(f"Database::db_import_sqlfile(sql_file={sql_file}, commit={commit}, rollback={rollback}, close_cursor={close_cursor})")

        if not os.path.exists(sql_file):
            return (False, f"The file {sql_file} does not exist.")

        state = False
        db_error = False
        db_message = None
        _msg = None

        with open(sql_file, encoding='utf8') as f:
            sql_data = f.read()
            f.close()
            sql_commands = sql_data.split(';\n')
            # remove all lines with '--' prefix (SQL comments)
            # replace \n and strip lines
            sql_commands = [x.replace("\n", "").strip() for x in sql_commands if not x.replace("\n", "").strip().startswith("--")]

            for command in sql_commands:
                state = False
                db_error = False
                db_message = None

                if command:
                    # self.module.log(f"execute statement: '{command}'")
                    (state, db_error, db_message) = self.db_execute(query=command, commit=commit)
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
            _msg = f"Cannot import file '{sql_file}' : {to_native(db_message)}"
        else:
            file_name = os.path.basename(sql_file)
            _msg = f"file '{file_name}' successful imported."

        return (state, _msg)

    def check_table_schema(self, database_table_name):
        """
            :return:
                - state (bool)
                - db_error(bool)
                - db_error_message = (str|none)
        """
        state = False
        db_error = False
        db_error_message = ""

        q = f"SELECT * FROM information_schema.tables WHERE table_name = '{database_table_name}'"

        number_of_rows = 0

        try:
            number_of_rows = self.db_cursor.execute(q)
            self.db_cursor.fetchone()

        except mysql_driver.Warning as e:
            try:
                error_id = e.args[0]
                error_msg = e.args[1]
                self.module.log(msg=f"WARNING: {error_id} - {error_msg}")
                pass
            except Exception:
                self.module.log(msg=f"WARNING: {str(e)}")
                pass

        except mysql_driver.Error as e:
            try:
                error_id = e.args[0]
                error_msg = e.args[1]

                if error_id == 1050:  # Table '...' already exists
                    self.module.log(msg=f"WARNING: {error_msg}")
                    pass
            except Exception:
                self.module.log(msg=f"ERROR: {str(e)}")
                pass

        except Exception as e:
            self.module.log(f"Cannot execute SQL '{q}' : {to_native(e)}")
            pass

        if number_of_rows == 1:
            state = True
            db_error = False
            db_error_message = f"The database schema '{database_table_name}' has already been created."

        return (state, db_error, db_error_message)
