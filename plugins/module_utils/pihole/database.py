
from pathlib import Path
import sqlite3
from typing import Any, Optional


class DataBase:
    def __init__(self, module: Any, database: str):
        self.module = module

        # self.module.log(f"DataBase::__init__(module, database={database})")

        db_file = Path(database)

        if not db_file.exists():
            raise FileNotFoundError(f"Pi-hole DB not found at: {db_file}")

        self.conn = sqlite3.connect(
            db_file,
            isolation_level=None,
            detect_types=sqlite3.PARSE_COLNAMES
        )
        self.cursor = self.conn.cursor()

    def execute(self, query: str, params: tuple = ()):
        """
        """
        # self.module.log(f"DataBase::execute(query={query}, params={params})")
        try:
            self.cursor.execute(query, params)
        except sqlite3.DatabaseError as e:
            error_details = {
                "error": str(e),
                "query": query,
                "params": params
            }
            self.module.fail_json(msg="Database query failed", **error_details)

    def fetchall(self):
        """
        """
        # self.module.log("DataBase::fetchall()")
        return self.cursor.fetchall()

    def fetchone(self):
        """
        """
        # self.module.log("DataBase::fetchone()")
        return self.cursor.fetchone()

    def commit(self):
        """
        """
        # self.module.log("DataBase::commit()")
        self.conn.commit()

    def close(self):
        """
        """
        # self.module.log("DataBase::close()")
        self.conn.close()

    def get_id_by_column(self, table: str, column: str, value: Any) -> Optional[int]:
        """
        """
        # self.module.log(f"DataBase::get_id_by_column(table={table}, column={column}, value={value})")

        query = f'SELECT id FROM "{table}" WHERE {column} = ?'
        self.execute(query, (value,))
        row = self.fetchone()
        return row[0] if row else None
