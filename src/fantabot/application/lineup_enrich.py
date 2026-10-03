"""The Classic extras on top of `build_inputs`: the lega's scoring rules and the predictor.

Two reads the plain `indexCompare` plan does without, kept apart so every surface that builds
a plan — `lineup plan`, `lineup submit`, `lineup submit-all`, `GET /lineup/plan`,
`POST /lineup/submit` — gets them from one place rather than each growing its own copy:

* **the rules** — `settings/calculate` parsed by `domain/lineup/rules`: the modificatore
  difesa's table, the substitution cap, the captain modifier. A failed read or an unreadable
  table is a *warning*, never a stop: a missing bonus table must not keep the lineup out.
* **the predictions** — `domain/lineup/predict` over the `lineUpInfo` rows, with last
  season's history from the database. An empty history (a fresh database) is not an error:
  every factor it feeds goes neutral and the forecast rests on the row's own signals.

Both are Classic only. Nothing here presents: warnings go to the injected `warn`.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.orm import Session

    from fantabot.adapters.tokens.store import TokenStore
    from fantabot.application.lineup_planner import LineupInputs
    from fantabot.domain.lineup.predict import Prediction
    from fantabot.domain.lineup.rules import LeagueRules

Warn = Callable[[str], None]


def _silent(_: str) -> None:
    return None


def league_rules(store: TokenStore, league_id: int, *, warn: Warn = _silent) -> LeagueRules | None:
    """The lega's `settings/calculate`, parsed; None when it cannot be read. Every problem is
    passed to `warn` and the plan carries on with the fallback."""
    from fantabot.adapters.http import apileague
    from fantabot.domain.lineup.rules import rules_from_calculate
    from fantabot.domain.tokens.errors import ApiTimeout, ApiUnavailable

    try:
        rules = rules_from_calculate(apileague.calculate_settings(league_id, store=store))
    except (ApiUnavailable, ApiTimeout) as exc:
        warn(
            f"{league_id}: scoring rules unreadable ({exc}) — any back four is preferred, "
            "without weighing the bonus."
        )
        return None
    for problem in rules.problems:
        warn(f"{league_id}: {problem}")
    return rules


def load_predictions(
    session: Session,
    lineup_info: Sequence[Mapping[str, Any]],
    cmday: int,
    *,
    as_of: date | None = None,
    warn: Warn = _silent,
) -> dict[int, Prediction]:
    """Run `domain/lineup/predict` over a Classic `lineUpInfo`, with the database's history.

    `as_of` is also what turns `FANTABOT_LINEUP_SENTIMENT` on: `None` (the default — no
    scheduled or interactive caller currently omits it, but a future one might) is exactly
    `off`, no matter the setting, and `SentimentRepository.latest_sentiment` is never called
    — the same "disabled means zero queries" discipline as `LiveRefreshSources.news()`.

    * **`off`** — one `predict()` call, byte-for-byte what this returned before the feature
      existed.
    * **`shadow`** — two `predict()` calls (both pure, microseconds over ~30 rows): the
      returned predictions are the **baseline**'s, untouched, so the ranked XI is unaffected;
      each one's `factors` gains `news_weight`/`shadow_score` from the adjusted run, and a
      summary of the biggest movers goes to `warn`.
    * **`live`** — the adjusted predictions are returned and do rank the XI.
    """
    from fantabot.adapters.persistence.repositories.lineup_history import (
        LineupHistoryRepository,
    )
    from fantabot.config import LINEUP_SENTIMENT_VAR, live_setting
    from fantabot.domain.lineup.predict import (
        predict,
        previous_season,
        signals_from_row,
        team_rates,
    )
    from fantabot.domain.lineup.sentiment import LIVE, OFF, parse_sentiment_mode, top_movers

    rows = [signals_from_row(row) for row in lineup_info]
    ids = [r.pid for r in rows]
    repo = LineupHistoryRepository(session)
    season = repo.latest_season()
    if season is None:
        kwargs: dict[str, Any] = {"cmday": cmday, "prior_fantamedia": {}, "past_clubs": {}, "rates": {}}
    else:
        last = previous_season(season)
        kwargs = {
            "cmday": cmday,
            "prior_fantamedia": repo.prior_fantamedia(ids, last),
            "prior_vote": repo.prior_media_voto(ids, last),
            "past_clubs": repo.past_clubs(ids, season),
            "rates": team_rates(repo.fixture_scores(last)),
        }

    mode = parse_sentiment_mode(live_setting(LINEUP_SENTIMENT_VAR)) if as_of is not None else OFF
    if mode == OFF:
        return predict(rows, **kwargs)

    sentiment = repo.latest_sentiment(ids)
    if not sentiment:
        return predict(rows, **kwargs)

    baseline = predict(rows, **kwargs)
    adjusted = predict(rows, sentiment=sentiment, as_of=as_of, **kwargs)
    if mode == LIVE:
        return adjusted

    movers = top_movers(
        {pid: p.score for pid, p in baseline.items()},
        {pid: p.score for pid, p in adjusted.items()},
    )
    if movers:
        names = {int(row["pid"]): str(row.get("plyr") or row["pid"]) for row in lineup_info}
        detail = ", ".join(f"{names.get(pid, pid)} {b:.2f}->{a:.2f}" for pid, b, a in movers)
        warn(f"sentiment (shadow, FANTABOT_LINEUP_SENTIMENT=shadow, not applied): {detail}")

    return {
        pid: dataclasses.replace(
            pred,
            factors={
                **pred.factors,
                "news_weight": adjusted[pid].factors["news_weight"],
                "shadow_score": adjusted[pid].score,
            },
        )
        for pid, pred in baseline.items()
    }


def enrich(
    inputs: LineupInputs,
    store: TokenStore,
    league_id: int,
    lineup_info: Sequence[Mapping[str, Any]],
    *,
    session: Session,
    predict: bool = True,
    warn: Warn = _silent,
    as_of: date | None = None,
) -> LineupInputs:
    """`inputs` with the lega's rules and, when `predict`, the predictions attached.

    A Mantra lega is returned unchanged: the rules table and the predictor are Classic only
    — which is also what keeps `FANTABOT_LINEUP_SENTIMENT` from ever touching a Mantra lega,
    since it is only ever read inside `load_predictions`, below this guard.
    `predict=False` is the `--no-predict` ablation — the rules still apply, so a back four
    still ranks first where the modifier is played, but nothing is weighed.
    """
    from fantabot.application.lineup_planner import with_rules

    if inputs.fmt != "classic":
        return inputs
    rules = league_rules(store, league_id, warn=warn)
    if rules is not None:
        inputs = with_rules(inputs, rules)
    if predict:
        inputs = dataclasses.replace(
            inputs,
            predictions=load_predictions(
                session, lineup_info, inputs.cmday, as_of=as_of, warn=warn
            ),
        )
    return inputs
