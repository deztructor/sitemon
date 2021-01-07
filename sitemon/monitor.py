import argparse
import asyncio
from dataclasses import asdict
import datetime
import enum
import logging
import re
import typing

import httpx

from sitemon.common import (
    read_json_file,
    SiteStatus,
    STATUS_TOPIC_NAME,
)
from sitemon import kafka


_log = logging.getLogger(__name__)


class AuxHttpCode(enum.IntEnum):
    """
    Additional HTTP pseudo-codes for exceptional situations.

    These codes are chosen to be compatible with ones used by Cloudflare.
    """

    Down = 521


def _now():
    """Make easier to mock now()."""
    return datetime.datetime.now()


async def monitor_and_publish(
        send_async: typing.Callable,
        http_get_async: typing.Callable,
        url: str,
        match: typing.Optional[str] = None,
) -> datetime.datetime:
    """
    Monitor web site and publish metrics.

    :param send_async: Coroutine publishing site check results to the provided topic.
    :param http_get_async: Corouting to send HTTP(S) GET request.
    :param url: monitored site URL;
    :param match: optional regular expression to search in the response text.
    :returns: moment when check began

    """
    start_time = _now()
    is_match_found = False
    try:
        response = await http_get_async(url)
        status_code = response.status_code
        is_match_found = (
            not match
            or re.search(match, response.text) is not None
        )
        latency_s = response.elapsed.total_seconds()
    except httpx.ConnectError:
        status_code = AuxHttpCode.Down
        latency_s = -1

    msg = SiteStatus(
        url=url,
        http_code=int(status_code),
        match=match or '',
        is_match_found=is_match_found,
        check_time_iso=start_time.isoformat(),
        latency_s=latency_s,
    )
    await send_async(STATUS_TOPIC_NAME, asdict(msg))
    return start_time


async def _wait_until_passed(
        check_interval_s: float,
        start_time: datetime.datetime,
) -> None:
    done_time = _now()
    time_passed_s = (done_time - start_time).total_seconds()
    if time_passed_s < 0:
        _log.warning("Maybe clock was changed")
        return
    sleep_interval_s = check_interval_s - time_passed_s
    if sleep_interval_s > 0:
        _log.debug('Waiting for %d s till the next check', sleep_interval_s)
        await asyncio.sleep(sleep_interval_s)


def _parse_args(args=None):
    parser = argparse.ArgumentParser()
    kafka.add_kafka_argument(parser)
    parser.add_argument("--url", type=str, required=True)
    parser.add_argument("--interval", type=float, default=60)
    parser.add_argument("--match")
    return parser.parse_args(args)


async def monitor_one_site(
        server: kafka.Server,
        url: str,
        interval: float = 60,
        match: typing.Optional[str] = None,
        is_stop_loop: typing.Callable = lambda: False,
):
    """
    Monitor site metrics.

    :param server: Kafka server metadata
    :param url: full URL of the monitored site
    :param interval: interval between site checks, in seconds;
    :param: regexp to search in the response or None/'' if no search needed
    :param is_stop_loop: function returning True to stop loop

    Monitoring is performed in infinite loop. If check loop took longer than
    `check_interval_s`, next check is done immediately.
    """
    server.register_topic(STATUS_TOPIC_NAME)
    producer = server.get_producer()
    async with producer:
        async with httpx.AsyncClient() as client:
            while True:
                start_time = await monitor_and_publish(
                    send_async=producer.send,
                    http_get_async=client.get,
                    url=url,
                    match=match,
                )
                if is_stop_loop():
                    break
                await _wait_until_passed(interval, start_time)


def main():
    """Execute CLI app for single site monitoring."""
    args = _parse_args()
    asyncio.run(monitor_one_site(
        server=kafka.Server(**read_json_file(args.kafka_conn)),
        url=args.url,
        interval=args.interval,
        match=args.match,
    ))


if __name__ == "__main__":
    main()
