# -*- coding:utf-8 -*-

#############################################################################

import sqlite3
from Logger import LOG

#############################################################################

class DriverExceptionHander(Exception): pass

class CursorContext:
    def __init__(self, connection):
        self.connection = connection
        self.cursor = connection.cursor()

    def __enter__(self):
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cursor.close()



class SQLite:
    def __init__(self, config):
        self._config    = config
        self._conn      = None

        self.connect()


    def connect(self):
        try:
            if self._conn is None:
                self._conn = sqlite3.connect(**self._config)

        except Exception as e:
            raise DriverExceptionHander('Can`t connect SQLite')


    def query(self, q, p=()):
        try:
            with CursorContext(self._conn) as cur:
                cur.execute(q, p)
                rows = cur.fetchall()
                self._conn.commit()

                return rows

        except Exception as e:
            LOG.info(f"QueryError#{e}###{q}###{','.join(map(str, p))}")
            self._conn.rollback()
            return False


    def close(self):
        if self._conn:
            self._conn.close()
