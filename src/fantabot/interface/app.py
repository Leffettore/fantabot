from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from fantabot.interface.console import console
from fantabot.interface.lineup import register as register_lineup_commands

if TYPE_CHECKING:
    from datetime import datetime

    import httpx

    from fantabot.adapters.tokens.store import TokenStore

# `pretty_exceptions_show_locals=False` is load-bearing, not cosmetic: an uncaught
# exception raised while a frame holds `headers = {"Authorization": "Bearer <token>"}`
# (an unmapped httpx/JSON error) would otherwise have Typer's rich handler print that
# frame's locals — the bearer — to stderr and any cron log. Typer's default has been
# `True` in versions the `typer>=0.12` pin allows, so the guarantee is pinned here in code
# rather than left to whichever Typer resolves. See `adapters/http/apileague._send`.
app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)


def _enable_os_trust_store() -> None:
    """Route TLS verification through the operating system's trust store.

    A corporate proxy (Zscaler, on the operator's Windows Enterprise machine)
    re-signs every TLS certificate with a private root that lives in the Windows
    store but not in certifi, so `httpx`'s default verification fails with a bare
    `TransportError` — which `apileague` surfaces as "returned 0", blaming the
    server for a problem that is entirely local. Loading the Windows store into
    OpenSSL by hand does not help either: OpenSSL 3.5 rejects the Zscaler CA
    ("Basic Constraints of CA cert not marked critical") where schannel accepts
    it. `truststore` sidesteps both by delegating verification to the OS, so this
    is a no-op on a machine with no interception and the correct default anywhere.

    Called from the root callback rather than at import time so it runs once per
    real CLI invocation, before any command builds an httpx client, and never as
    a side effect of importing `app` in a test.
    """
    import truststore

    truststore.inject_into_ssl()


@app.callback()
def _main() -> None:
    """Root callback: make every command's TLS verification use the OS trust store."""
    _enable_os_trust_store()

auth_app = typer.Typer(no_args_is_help=True, help="Sign in; manage stored credentials.")
lineup_app = typer.Typer(no_args_is_help=True, help="Read, plan and submit the weekly formazione.")


def token_status_rows(
    store: TokenStore,
    *,
    now: datetime,
    verify: bool = False,
    transport: httpx.BaseTransport | None = None,
) -> list[tuple[str, str, str, str]]:
    """The rendered table body. **This is the injection point.**

    A Typer command has nowhere to accept a transport, so the work lives here
    and the command is a thin shell over it. `--verify` fires exactly one
    request per stored row; without it, nothing is built at all.
    """
    from fantabot.adapters.http import apileague as apileague
    from fantabot.domain.tokens.errors import TokenError
    from fantabot.domain.tokens.status import orphaned, render_state

    rows = store.status()
    stale = orphaned(rows)
    fingerprint = store.key_fingerprint

    rendered: list[tuple[str, str, str, str]] = []
    for row in rows:
        state = render_state(
            row, now=now, key_fingerprint=fingerprint, is_orphaned=row.league_id in stale
        )
        if verify:
            try:
                apileague.league_status(
                    row.league_id, store=store, transport=transport, now=now
                )
                store.mark_verified(row.league_id, now)
                state = f"{state} · verified"
            except TokenError as exc:
                # Replace rather than append when the local verdict was "ok".
                # Seen on a real run: "ok (357d) · apileague rejected the token"
                # reads as a contradiction. The local check and the server's
                # answer are two different facts, and when they disagree the
                # server's is the one that matters.
                state = f"REJECTED — {exc}" if state.startswith("ok") else f"{state} · {exc}"
        rendered.append(
            (
                str(row.league_id),
                row.league_name or "—",
                f"{row.expires_at:%Y-%m-%d}",
                state,
            )
        )
    return rendered


def token_status(
    league: int = typer.Option(0, "--league", help="Only this lega's row."),
    verify: bool = typer.Option(
        False, "--verify", help="Also call the API once per row to prove the token works."
    ),
) -> None:
    """What is stored, when it expires, and whether it still works.

    Reads only the database, so it works with the browser closed and the site
    down — and because `expires_at` is a plaintext column, it still reports
    expiry with `FANTABOT_ENCRYPTION_KEY` absent. That is the situation where a
    straight answer matters most.
    """
    from datetime import UTC, datetime

    from rich.table import Table
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import SQLAlchemyError

    from fantabot.adapters.persistence import database_manager
    from fantabot.adapters.tokens.store import TokenStore
    from fantabot.config import settings
    from fantabot.domain.tokens.crypto import TokenCipher
    from fantabot.domain.tokens.errors import TokenError
    from fantabot.domain.tokens.status import MISSING

    # No key is not an error here. The whole point of the plaintext expiry
    # columns is that this command still answers without one.
    cipher = None
    if settings.fantabot_encryption_key:
        try:
            cipher = TokenCipher(settings.fantabot_encryption_key)
        except TokenError as exc:
            console.print(f"[yellow]{exc}[/yellow]")
    else:
        console.print(
            "[yellow]FANTABOT_ENCRYPTION_KEY is not set — expiries below are still "
            "accurate; nothing can be decrypted.[/yellow]"
        )

    try:
        with database_manager.get_session() as session:
            rows = token_status_rows(
                TokenStore(session, cipher), now=datetime.now(UTC), verify=verify
            )
    except SQLAlchemyError as exc:
        dsn = make_url(settings.fantabot_database_url).render_as_string(hide_password=True)
        console.print(f"[red]Cannot reach the database at {dsn}[/red]")
        console.print(f"[red]{type(exc).__name__}: {str(exc).splitlines()[0]}[/red]")
        console.print("Start it with: [bold]fantabot-app db start[/bold]")
        raise typer.Exit(code=1) from None

    wanted = league or settings.fantabot_league_id
    if wanted:
        rows = [r for r in rows if r[0] == str(wanted)]
        if not rows:
            # A lega is only *known* to exist if you named it or .env did.
            rows = [(str(wanted), "—", "—", MISSING)]

    if not rows:
        console.print("[yellow]No tokens stored — run [bold]fantabot auth login[/bold].[/yellow]")
        return

    table = Table("lega", "name", "expires", "state")
    for row in rows:
        table.add_row(*row)
    console.print(table)

    if any(MISSING in row[3] or "ORPHANED" in row[3] for row in rows):
        console.print(
            "[dim]ORPHANED = the token is still valid, but a later login did not find "
            "that lega on the account. Nothing is deleted automatically; remove it "
            "with [bold]fantabot auth forget --league <id>[/bold].[/dim]"
        )


def login(
    league: int = typer.Option(0, "--league", help="Only capture this lega."),
    force: bool = typer.Option(False, "--force", help="Re-auth even if the token is valid."),
    verify: bool = typer.Option(
        True, "--verify/--no-verify", help="Confirm each stored token against the API."
    ),
    save_session: bool = typer.Option(
        False, "--save-session", help="Also write data/storage_state.json (default: off)."
    ),
) -> None:
    """Sign in once; store every lega's bearer token encrypted in Postgres.

    Replaces the old `auth` command. You log in yourself in a real browser —
    nothing here scripts a credential, and nothing clicks anything after you do.
    The token is then read from localStorage, encrypted and written to
    `league_tokens`, keyed by lega.

    Running it again when every token is still valid opens no browser at all.
    """
    from fantabot.adapters.browser.capture import read_storage_state, real_browser
    from fantabot.application import auth_login as login_module
    from fantabot.application.login_wait import CaptureUnreadable
    from fantabot.domain.tokens.errors import SignInWindowClosed, TokenError

    try:
        login_module.run(
            browser_factory=real_browser,
            read_state=read_storage_state,
            league=league,
            force=force,
            verify=verify,
            save_session=save_session,
            report=console,
        )
    except login_module.LoginAborted as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=exc.code) from None
    except (SignInWindowClosed, CaptureUnreadable) as exc:
        # Reported apart from TokenError so the message names what the human did,
        # rather than "no leghe found in the browser session".
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None
    except TokenError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None


def token_forget(
    league: int = typer.Option(0, "--league", help="The lega whose row to remove."),
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt."),
) -> None:
    """Remove one lega's stored token: that row, and nothing else.

    Deliberate, one at a time. There is no `--all` and no wildcard, on purpose.
    Removal is manual because a `leagues[]` that came back short — a partial
    load, an API blip — would otherwise silently destroy a working token, and
    re-login is the only recovery. Keeping a dead row costs a line of output;
    deleting a live one costs a credential.

    The app's Disconnect button is not this command. It calls DELETE
    /auth/league/{id}, which removes the token and then purges the lega across
    six tables: league_snapshot, league_team_snapshot, league_player_pool,
    league_custom_role, league_competition and league_fixture. Two similar names
    for two different acts — this one leaves all six standing, and a re-login
    undoes it.
    """
    from datetime import UTC, datetime

    from fantabot.adapters.persistence import database_manager
    from fantabot.adapters.tokens.store import TokenStore
    from fantabot.domain.tokens.status import render_state

    if not league:
        console.print("[red]--league is required. There is no --all.[/red]")
        raise typer.Exit(code=2)

    with database_manager.get_session() as session:
        store = TokenStore(session)
        row = next((r for r in store.status() if r.league_id == league), None)

        if row is None:
            console.print(
                f"[yellow]No stored token for lega {league} — nothing to remove.[/yellow]"
            )
            return

        # Lega, name and expiry only: never the ciphertext, never the fingerprint.
        state = render_state(row, now=datetime.now(UTC), key_fingerprint=None)
        console.print(f"{row.league_id}  {row.league_name or '—'}  {state}")

        if not yes and not typer.confirm(f"Remove the stored token for lega {league}?"):
            console.print("Nothing removed.")
            return

        store.forget(league)

    console.print(f"[green]Removed the stored token for lega {league}.[/green]")


app.add_typer(auth_app, name="auth")
app.add_typer(lineup_app, name="lineup")
auth_app.command("login")(login)
auth_app.command("status")(token_status)
auth_app.command("forget")(token_forget)
register_lineup_commands(lineup_app)


if __name__ == "__main__":
    app()
