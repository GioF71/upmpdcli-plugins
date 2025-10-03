# Copyright (C) 2025 Giovanni Fulco
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import sqlite3
import sqlhelper


def __sqlite3_execute_update(
        connection: sqlite3.Connection,
        sql: str,
        data: tuple,
        cursor=None,
        do_commit: bool = True):
    the_cursor = cursor if cursor else connection.cursor()
    the_cursor.execute(sql, data)
    if not cursor:
        the_cursor.close()
    if do_commit:
        connection.commit()


def __sqlite3_select(
        connection: sqlite3.Connection,
        sql: str,
        parameters: tuple) -> list[any]:
    cursor = connection.cursor()
    cursor.execute(sql, parameters)
    rows = cursor.fetchall()
    cursor.close()
    return rows if rows else []


def get_sqlite3_executor(connection: sqlite3.Connection) -> sqlhelper.SqlExecutor:
    return lambda sql, data, do_commit: __sqlite3_execute_update(
        connection=connection,
        sql=sql,
        data=data,
        do_commit=do_commit)


def get_sqlite3_selector(connection: sqlite3.Connection) -> sqlhelper.SqlSelector:
    return lambda sql, parameters: __sqlite3_select(
        connection=connection,
        sql=sql,
        parameters=parameters)
