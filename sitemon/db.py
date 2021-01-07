import argparse
import asyncio
import contextlib
from dataclasses import dataclass
import datetime
import logging
import sys
import typing

import asyncpg  # type: ignore

from sitemon.common import (
    read_json_file,
    SiteStatus,
)


_log = logging.getLogger(__name__)

_CREATE_INSERT_PROCEDURE = """
create or replace procedure insert_status(
    site_url text, match text, check_time timestamptz,
    http_code integer, latency float, is_expression_found bool)
language plpgsql as $$
declare
    info_id integer := null;
begin
    select id into info_id from site_info
        where url = site_url and search_expression = match limit 1;
    if info_id is null then
        with new_id as (
            insert into site_info(url, search_expression)
            values (site_url, match)
            returning id
        )
        select * from new_id into info_id;
    end if;
    insert into site_state(site_info_id, check_time, http_code, latency, is_expression_found)
        values (info_id, check_time, http_code, latency, is_expression_found);
end;
$$
"""

# if information should be requested from the database, index should be created for the url field
_CREATE_TABLES_QUERY = """
create table site_info (
    id serial unique,
    url text not null,
    search_expression text,
    primary key (url, search_expression)
);

create table site_state (
    id bigserial unique,
    site_info_id integer references site_info (id) not null,
    check_time timestamptz not null,
    http_code integer not null,
    latency float not null,
    is_expression_found bool
);
"""

USER_DB_JSON_EXAMPLE = """
{
    "user": "avnadmin",
    "password": "",
    "database": "defaultdb"
}
"""

_DB_CONN_JSON_EXAMPLE = """
{
    "host": "somehost.aivencloud.com",
    "port": 13862,
    "is_ssl": true
}
"""


@dataclass(frozen=True)
class Dsn:
    """Info to construct DSN."""

    host: str
    port: int
    user: str
    password: str
    database: typing.Optional[str] = None
    is_ssl: bool = True

    def __str__(self):
        ssl_option = 'sslmode=require' if self.is_ssl else ''
        database = self.database or ''
        return (
            f"postgres://{self.user}:{self.password}@{self.host}:{self.port}/"
            f"{database}?{ssl_option}"
        )


@dataclass(frozen=True)
class Db:
    """Info to create database"""

    user: str
    password: str
    database: str

    async def recreate(self, connection: asyncpg.Connection):
        """
        Create database and user for site monitor

        :param dsn: DSN providing privilegies to create DB

        """

        # queries are separate to keep them in a separate transactions
        queries = [
            f"drop database if exists {self.database};",
            f"drop user if exists {self.user};",
            f"create database {self.database};",
            f"create user {self.user} with encrypted password '{self.password}';",
            f"grant all privileges on database {self.database} to {self.user};",
        ]
        for query in queries:
            await connection.execute(query)


@contextlib.asynccontextmanager
async def connection_context(dsn: typing.Union[str, Dsn]) -> asyncpg.Connection:
    """
    Provide context for opened connection to the database.

    :param dsn: defines database/connection properties
    :returns: opened connection

    """

    connection = await asyncpg.connect(dsn=str(dsn))
    try:
        yield connection
    finally:
        await connection.close()


@dataclass(frozen=True)
class SiteState:
    """
    Database access for site monitor recorder

    Group all functionality required for tables and procedures creation.
    """

    connection: asyncpg.Connection

    async def try_init(self):
        """
        Initialize database tables, stored procedures.

        Creates site monitor tables if they don't exist. Also create/replace
        stored procedure, used to insert site status data.

        """
        try:
            await self.connection.execute(_CREATE_TABLES_QUERY)
        except asyncpg.exceptions.DuplicateTableError:
            _log.debug("Tables already exist")

        await self.connection.execute(_CREATE_INSERT_PROCEDURE)

    async def insert_site_status(self, status: SiteStatus):
        """Save site status to the database tables."""
        await self.connection.execute(
            "call insert_status($1, $2, $3, $4, $5, $6);",
            status.url,
            status.match,
            datetime.datetime.fromisoformat(status.check_time_iso),
            status.http_code,
            status.latency_s,
            status.is_match_found,
        )


def add_db_conn_argument(parser: argparse.ArgumentParser):
    """Add documented DB connection JSON parameter to ArgumentParser."""
    parser.add_argument(
        "--db-conn",
        required=True,
        help=(
            "JSON file describing PostgreSQL DB connection in the format:\n\n"
            + _DB_CONN_JSON_EXAMPLE
        ),
    )


def recreate(args=None):
    """Create or recreate database and user for site monitor."""

    parser = argparse.ArgumentParser()
    add_db_conn_argument(parser)
    parser.add_argument(
        "--admin",
        required=True,
        help=(
            "JSON file describing user that has privileges to create DB in the format:\n\n"
            + USER_DB_JSON_EXAMPLE
        ),
    )
    parser.add_argument(
        "db",
        help=(
            "JSON file with new DB description in the format:\n\n"
            + USER_DB_JSON_EXAMPLE
        )
    )
    info = parser.parse_args(args)
    asyncio.run(recreate_db(info.db_conn, info.admin, info.db))
    sys.exit(0)


async def recreate_db(db_conn, admin, db):
    """Re-creates database and user from scratch."""
    dsn = Dsn(**read_json_file(db_conn), **read_json_file(admin))
    db = Db(**read_json_file(db))
    async with connection_context(dsn) as connection:
        await db.recreate(connection)
