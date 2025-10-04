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


from typing import Protocol


class SqlExecutor(Protocol):
    def __call__(
            self,
            sql: str,
            data: tuple,
            do_commit: bool) -> None:
        ...


class SqlSelector(Protocol):
    def __call__(
            self,
            sql: str,
            parameters: tuple) -> list[any]:
        ...


def create_simple_insert_sql(
        table_name: str,
        column_list: list[str]) -> str:
    return f"""
        INSERT INTO
            {table_name}
            ({", ".join(column_list)})
        VALUES
            ({", ".join('?' * len(column_list))})
    """


def create_simple_delete_sql(
        table_name: str,
        where_colum_list: list[str]) -> str:
    return f"""
        DELETE FROM
            {table_name}
        WHERE
            {" AND ".join(list(map(_append_question_mark, where_colum_list)))}
    """


def create_simple_update_sql(
        table_name: str,
        set_column_list: list[str],
        where_colum_list: list[str]) -> str:
    return f"""
        UPDATE
            {table_name}
        SET
            {", ".join(list(map(_append_question_mark, set_column_list)))}
        WHERE
            {" AND ".join(list(map(_append_question_mark, where_colum_list)))}
    """


def create_simple_select_sql(
        table_name: str,
        select_column_list: list[str],
        where_colum_list: list[str] = None) -> str:
    sql: str = f"""
        SELECT
            {", ".join(select_column_list)}
        FROM {table_name}
    """
    if where_colum_list and len(where_colum_list) > 0:
        sql = f"""
            {sql}
            WHERE
                {" AND ".join(list(map(_append_question_mark, where_colum_list)))}
            """
    return sql


def _append_question_mark(column_name: str) -> str:
    return f"{column_name} = ?"


def neutral_execute_update(
        sql_executor: SqlExecutor,
        sql: str,
        data: tuple,
        do_commit: bool = True):
    sql_executor(
        sql=sql,
        data=data,
        do_commit=do_commit)


def neutral_select(
        sql_selector: SqlSelector,
        sql: str,
        parameters: tuple) -> list[any]:
    sql_selector(
        sql=sql,
        parameters=parameters)
