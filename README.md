# Site Monitor

Simple test application providing capability to monitor a web site.
It passes monitoring data through the network by means of Kafka.
And stores results in PostgreSQL database.

## Installation

This project uses `poetry` for dependencies management and packaging.
This tool should be installed for development/testing and packaging.
Installation of `poetry` is described in the [poetry documentation](https://python-poetry.org/docs/#installation).

While the simplest way to setup both poetry and development environment for the package could be:

``` sh
cd SITEMON_GIT_ROOT
python3 -m venv PATH_TO_POETRY_VENV
. PATH_TO_POETRY_VENV/bin/activate
pip install poetry
poetry install
```

## Dependencies

This project was created using python 3.8 currently installed on my system, so it was tested only with this version.

Because of the I/O bound nature of the project, usage of asynchronous I/O could be the best option for it.
This is the reason why the following libraries were chosen:

- `aiokafka` to support Kafka;
- `httpx` to send HTTP(S) requests;
- `asyncpg` to work with PostgreSQL.

`pytest` is used for unit tests.
`tidypy` was chosen as a basic code quality analysis framework (instead of e.g. `prospector`) because:

- I wanted to try this tool in practice;
- it has integration with `pytest` and `pyproject.toml`.

## Configuration

Directory `conf_templates` contains file "templates".
They represent set of configuration files required to run site monitor.
These files can be copied to protected configuration directory, inaccessible by other users.
And filled with proper metadata/credentials.

- `pg-server.json` - PostgreSQL server information;
- `db-admin.json` - credentials of PostgreSQL user who has rights to create users/databases;
- `sitemon-db.json` - site monitor database name, and site monitor user credentials;
- `kafka-server.json` - Kafka server information and access credentials.

Also if connection to Kafka is using SSL + client SSL authentication, there should be following files:

- CA certificate used for server authentication;
- certificate used for client authentication;
- key (secret) used for client authentication.

For simplicity the same user is used to access Kafka.

## Run

Example:

``` sh
# CONF_DIR=<path to configuration files dir>

# delete sitemon user and DB, re-create it from scratch
poetry run recreate-sitemon-db --db-conn $CONF_DIR/pg-server.json --admin $CONF_DIR/db-admin.json $CONF_DIR/sitemon-db.json

# run site monitor in the background
poetry run sitemon-monitor --kafka-conn $CONF_DIR/kafka-server.json --url http://localhost --interval 1 &

# run DB data recorder
poetry run sitemon-recorder --db-conn $CONF_DIR/pg-server.json --kafka $CONF_DIR/kafka.json $CONF_DIR/sitemon-db.json
```

## Testing

There is a GitHub CI workflow running unit tests and static/style checks for the project.
To run them manually (assuming that development environment is installed by poetry), run:

``` sh
poetry run pytest --disable-pytest-warnings --tidypy --mypy
```

## TODO

- Service scripts do not try to re-connect to Kafka and PostgreSQL if connection is interrupted;
- Monitoring script could be changed to concurrently monitor multiple sites in the same asyncio loop re-using the same Kafka connection;
- Parallelism on multi-core systems can be achieved by using Python `multiprocessing`;
