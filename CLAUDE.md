# CLAUDE.md

`fantabot` is a Python ≥3.11 Typer CLI that submits the weekly fantacalcio lineup on
`leghe.fantacalcio.it`. Console script: `fantabot` → `fantabot.interface.app:app`.

## Commands

```bash
pip install -e ".[dev]"
fantabot auth login
fantabot auth status
fantabot auth forget --league 4103937
fantabot lineup leagues
fantabot lineup rules
fantabot lineup submit-all --arm --refresh
pytest
ruff check src tests
mypy
alembic upgrade head
```

## Architecture

Four layers, dependencies pointing inward, enforced by `tests/test_layers.py`:

* `domain/` pure: no I/O, network, clock or framework imports (`lineup`, `tokens`, `lega`,
  `classic`, `news`, `shared`, a few `asta`/`mantra` helpers).
* `application/` use cases (`lineup_submit`, `lineup_enrich`, `lineup_refresh`, `auth_login`, ...).
* `adapters/` the outside world: `http/apileague`, `persistence`, `tokens`, `browser`, `agent`, `files`, `scraping`.
* `interface/` Typer only (`app`, `lineup`, `console`).

## Rules

* Submission needs `FANTABOT_AUTO_ACT=true` **and** `--arm`; never change the default.
* `auth login` stays manual and headed. A bearer token is never printed, logged or committed
  (`tests/adapters/tokens/test_token_secrecy.py`).
* Domain logic stays pure; the test suite opens zero sockets and makes zero agent calls.
* Every importer and repository write is an upsert.
* `FANTABOT_DATABASE_URL` (psycopg2) and `FANTABOT_ENCRYPTION_KEY` are set explicitly; there is no bundled database.
