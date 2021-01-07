"""Contains functionality used by all modules."""

from dataclasses import dataclass


#: Topic used to pass monitored status Kafka messages.
STATUS_TOPIC_NAME = 'sitemon.site.status'


@dataclass(frozen=True)
class SiteStatus:
    """Structure of the message representing monitored site status."""

    url: str
    """URL of the monitored web site."""

    check_time_iso: str
    """Date/time when HTTP(S) request was sent in ISO format."""

    http_code: int
    """HTTP code of the response to the GET request."""

    latency_s: float
    """HTTP(S) request latency, in seconds."""

    match: str
    """Regular expression to search withing returned response.

    empty if no check is needed
    """

    is_match_found: bool
    """Indicate was text corresponding to `match` found."""
