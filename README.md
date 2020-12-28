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
