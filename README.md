# fantabot

Submits the weekly fantacalcio lineup on `leghe.fantacalcio.it` with no human in the loop.
A cron-driven bot with one interactive step: signing in.

## Setup

```bash
pip install -e ".[dev]"
playwright install chromium      # only needed on the machine where you sign in
cp .env.example .env             # set FANTABOT_DATABASE_URL and FANTABOT_ENCRYPTION_KEY
alembic upgrade head
```

## Commands

```bash
fantabot auth login              # headed, manual sign-in -> encrypted tokens in league_tokens
fantabot auth status             # stored / expires / state per lega
fantabot auth forget --league 4103937

fantabot lineup leagues          # classify every stored lega
fantabot lineup rules            # the lega's own modifier table and substitution cap
fantabot lineup plan             # what would be submitted
fantabot lineup submit-all       # dry run for every open lega
fantabot lineup submit-all --arm --refresh   # the weekly run
```

Submission needs two locks: `FANTABOT_AUTO_ACT=true` in the environment **and** `--arm`.
Without both it is a dry run. `--refresh` first refreshes voti, the lega and news.

## Scheduling (Linux)

`scripts/matchday.sh` runs the weekly job; `scripts/fantabot-matchday.{service,timer}` are
systemd units that fire it on Fridays at 09:00.

## Tests

```bash
pytest          # zero sockets, db tests deselected
ruff check src tests
mypy
```
