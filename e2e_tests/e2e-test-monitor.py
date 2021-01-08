#!/usr/bin/env python3

import argparse
import asyncio

from sitemon.common import read_json_file
from sitemon import (
    db,
    kafka,
    monitor,
    recorder,
)


def _parse_args(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, required=True)
    db.add_db_conn_argument(parser)
    kafka.add_kafka_argument(parser)
    parser.add_argument(
        "--admin",
        required=True,
        help=(
            "JSON file describing user that has privileges to create DB in the format:\n\n"
            + db.USER_DB_JSON_EXAMPLE
        ),
    )
    parser.add_argument(
        "db",
        help=(
            "JSON file with destination DB description in the format:\n\n"
            + db.USER_DB_JSON_EXAMPLE
        ),
    )
    return parser.parse_args(args)


async def _run_test(info):
    kafka_server = kafka.Server(**read_json_file(info.kafka_conn))
    dsn = db.Dsn(**read_json_file(info.db_conn), **read_json_file(info.db))

    await db.recreate_db(info.db_conn, info.admin, info.db)
    record_task = asyncio.create_task(
        recorder.collect_data(
            server=kafka_server,
            dsn=dsn,
            is_stop_loop=lambda: True,
        )
    )
    await asyncio.sleep(1)
    url = "https://google.com"
    await monitor.monitor_one_site(
        server=kafka_server,
        url=url,
        interval=1,
        match=r'html',
        is_stop_loop=lambda: True,
    )
    await record_task
    data = []
    async with db.connection_context(dsn) as connection:
        site_state = db.SiteState(connection)
        async for record in site_state.gen_url_state(info.url):
            data.append(record)
    assert len(data) == 1
    v = data[0]
    assert v['url'] == url
    assert v['latency'] > 0
    assert v['http_code'] == 200
    print('Got', data)


def main():
    """E2E test for one iteration of site status check."""
    asyncio.run(_run_test(_parse_args()))


if __name__ == '__main__':
    main()
