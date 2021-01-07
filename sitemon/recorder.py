"""Functionality to record sitew status events to the database."""
import argparse
import asyncio
import sys
import typing

from sitemon.common import (
    read_json_file,
    SiteStatus,
    STATUS_TOPIC_NAME,
)
from sitemon import (
    db,
    kafka,
)


async def collect_data(
        server: kafka.Server,
        dsn: db.Dsn,
        is_stop_loop: typing.Callable = lambda: False
):
    """
    Collect events from Kafka and store them to the database.

    :param is_stop_loop: function returning True to stop loop

    """
    consumer = server.get_consumer(STATUS_TOPIC_NAME)
    async with consumer:
        async with db.connection_context(dsn) as db_connection:
            site_state_db = db.SiteState(db_connection)
            await site_state_db.try_init()
            while True:
                msg = await consumer.getone()
                status = SiteStatus(**msg.value)
                await site_state_db.insert_site_status(status)
                if is_stop_loop():
                    break


def _parse_args(args=None):
    parser = argparse.ArgumentParser()
    db.add_db_conn_argument(parser)
    kafka.add_kafka_argument(parser)
    parser.add_argument(
        "db",
        help=(
            "JSON file with destination DB description in the format:\n\n"
            + db.USER_DB_JSON_EXAMPLE
        ),
    )
    return parser.parse_args(args)


def main():
    """Execute CLI app for site status recorder."""
    args = _parse_args()
    asyncio.run(collect_data(
        server=kafka.Server(**read_json_file(args.kafka_conn)),
        dsn=db.Dsn(**read_json_file(args.db_conn), **read_json_file(args.db)),
    ))
    sys.exit(0)


if __name__ == "__main__":
    main()
