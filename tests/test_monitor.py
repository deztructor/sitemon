from collections import namedtuple
from dataclasses import asdict
import datetime

import pytest
from asynctest import CoroutineMock  # type: ignore

from sitemon.common import (
    SiteStatus,
    STATUS_TOPIC_NAME,
)
from sitemon.monitor import (
    monitor_and_publish,
    _wait_until_passed,
)


@pytest.mark.asyncio
async def test_wait_until_passed(mocker, subtests):
    """Test wait logic."""
    now = datetime.datetime.now()
    plus_sec = now + datetime.timedelta(seconds=1)
    now_mock = mocker.patch('sitemon.monitor._now')
    sleep_mock = mocker.patch('asyncio.sleep', CoroutineMock())

    with subtests.test("Time moved back, shouldn't wait"):
        now_mock.return_value = now - datetime.timedelta(seconds=1)
        await _wait_until_passed(1, now)
        sleep_mock.assert_not_called()

    now_mock.return_value = plus_sec

    await _wait_until_passed(-0.1, now)
    sleep_mock.assert_not_called()

    await _wait_until_passed(1, now)
    sleep_mock.assert_not_called()

    await _wait_until_passed(2, now)
    sleep_mock.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_monitor(mocker, subtests):
    """Test sitemon.monitor.Monitor class."""

    Data = namedtuple('Data', 'explanation text expected_msg')
    data = [
        Data(
            'Empty message, no search for content',
            '',
            SiteStatus(
                url='foo',
                http_code=200,
                match='',
                is_match_found=True,
                check_time_iso=mocker.ANY,
                latency_s=1,
            ),
        ),
        Data(
            'Matched regexp should not be found',
            'foo bar foo',
            SiteStatus(
                url='foo',
                http_code=200,
                match=r'bar\w',
                is_match_found=False,
                check_time_iso=mocker.ANY,
                latency_s=1,
            ),
        ),
        Data(
            'Successfully find matching regexp',
            'foo bar foo',
            SiteStatus(
                url='foo',
                http_code=200,
                match=r'bar +f',
                is_match_found=True,
                check_time_iso=mocker.ANY,
                latency_s=1,
            ),
        ),
    ]

    text = None
    expected_msg = None

    def get_http_response_mock(url):
        assert url == expected_msg.url
        response = mocker.Mock()
        response.text = text
        response.status_code = expected_msg.http_code
        response.elapsed.total_seconds = mocker.Mock(return_value=expected_msg.latency_s)
        return response

    async def send_mock(topic, msg):
        assert topic == STATUS_TOPIC_NAME
        assert isinstance(msg, dict)
        try:
            status = SiteStatus(**msg)
        except Exception as err:  # pylint: disable=broad-except
            pytest.fail(err)

        assert msg == asdict(expected_msg)
        check_time = datetime.datetime.fromisoformat(status.check_time_iso)
        assert isinstance(check_time, datetime.datetime)

    http_get_mock = CoroutineMock(side_effect=get_http_response_mock)

    for current_row in data:
        explanation, text, expected_msg = current_row
        with subtests.test(
                msg="monitor_and_publish(): {}".format(explanation),
                data=current_row):
            start_date_time = await monitor_and_publish(
                send_async=send_mock,
                http_get_async=http_get_mock,
                url=expected_msg.url,
                match=expected_msg.match,
            )
            assert isinstance(start_date_time, datetime.datetime)
