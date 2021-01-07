"""Wrappers to create aiokafka producer/consumer from metadata."""
import argparse
import asyncio
from dataclasses import (
    asdict,
    dataclass,
)
import json
import typing

from aiokafka.consumer import AIOKafkaConsumer  # type: ignore
from aiokafka.helpers import create_ssl_context  # type: ignore
from aiokafka.producer import AIOKafkaProducer  # type: ignore

from kafka.admin import (  # type: ignore
    KafkaAdminClient,
    NewTopic,
)
from kafka.errors import TopicAlreadyExistsError  # type: ignore


_KAFKA_JSON_EXAMPLE = """
{
    "host": "somehost.aivencloud.com",
    "port": 13864,
    "ssl": {
        "cafile": "path-to/ca.pem",
        "certfile": "path-to/service.cert",
        "keyfile": "path-to/service.key"
    }
}
"""


@dataclass(frozen=True)
class SslContext:
    """
    Kafka SSL context metadata for AIOKafka.

    Field names match to parameters' names for `create_ssl_context()`
    """

    cafile: str
    certfile: str
    keyfile: str

    def create(self):
        """Create SSL context based on this description."""
        return create_ssl_context(**asdict(self))

    def as_kwargs(self):
        """Provide kwargs to create producer/consumer using SSL."""

        return {
            'security_protocol': 'SSL',
            'ssl_context': self.create(),
        }


@dataclass()
class Server:
    """Describes connection metadata for Kafka."""

    host: str
    port: int
    ssl: typing.Optional[SslContext] = None

    def __post_init__(self):
        if self.ssl is None:
            return
        if isinstance(self.ssl, dict):
            self.ssl = SslContext(**self.ssl)

    def as_kwargs(self):
        """Provide kwargs to create producer/consumer using SSL."""

        aux_kwargs = self.ssl.as_kwargs() if self.ssl else {}
        return {
            **aux_kwargs,
            'bootstrap_servers': f"{self.host}:{self.port}",
        }

    def register_topic(self, topic: str):
        """Register topic in Kafka."""
        admin = KafkaAdminClient(**self.as_kwargs())
        try:
            admin.create_topics(
                new_topics=[
                    NewTopic(
                        topic,
                        num_partitions=1,
                        replication_factor=1,
                    ),
                ],
                validate_only=False,
            )
        except TopicAlreadyExistsError:
            pass

    def get_producer(self):
        """Create producer based on the metadata."""
        return AIOKafkaProducer(
            loop=asyncio.get_event_loop(),
            value_serializer=_serialize,
            compression_type="gzip",
            **self.as_kwargs(),
        )

    def get_consumer(self, topic: str):
        """Create consumer based on the metadata."""
        return AIOKafkaConsumer(
            topic,
            loop=asyncio.get_event_loop(),
            value_deserializer=_deserialize,
            **self.as_kwargs(),
        )


def _serialize(data: dict) -> bytes:
    return json.dumps(data).encode()


def _deserialize(data: bytes) -> dict:
    return json.loads(data.decode())


def add_kafka_argument(parser: argparse.ArgumentParser):
    """Add documented Kafka connection JSON parameter to ArgumentParser."""
    parser.add_argument(
        "--kafka-conn",
        required=True,
        help=(
            "JSON file describing Kafka connection in the format:\n\n"
            + _KAFKA_JSON_EXAMPLE
        ),
    )
