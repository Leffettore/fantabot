"""Turn a news reading into a nudge on a Classic player's play probability. Pure.

`domain/lineup/predict.py::predict()`'s ``p_play`` already comes from the platform's own
probable-starter percentage (`lineUpInfo.percent`), which measurement shows already reflects
a confirmed injury or suspension. What a scraped reading can add is *earlier* knowledge — a
knock reported by a blog before the platform's own percentage catches up — so this module
nudges ``p_play`` toward the reading rather than replacing it outright.

The formula is `domain/lineup/presence.py`'s own — `cal()`'s titolarita-on-the-vote-scale and
the `(1-w)*d_eff*prior + w*tv` blend — applied to `p_play` in the role `presence()` gives
`p_hist`. It is not re-derived here because it is already reviewed, already shipped (behind
the `projection` surface), and a second, drifting copy of the same arithmetic is exactly the
failure mode this codebase keeps a written rule against (see `asta_planner.py`'s "one place
the value model is built").

**Deliberately not ported: the asta's *tilt*** (`sentiment`/`forma`/`mercato`/`rigorista`/
`piazzati` — "how well will he do", as opposed to "will he play"). `fv_if_plays` already
carries a partially measured baseline/opponent/venue model; stacking an ungrounded LLM
quality-read on top of it, with no lineup-side historical corpus to check the result against
(unlike votes/prices, `player_sentiment` has no archive for past seasons), risks corrupting a
component that has some grounding to correct one that has none. Availability is the
concrete, checkable half of a reading, and it is the half this module touches.

A silent or absent reading (`confidenza == 0`, or no row at all) leaves `p_play` exactly
untouched — not by a special case, but because the blend's own weight `w` is 0 in that case,
the same "no opinion moves nothing" identity `domain/asta/sentiment.py` proves for its own
gate.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from fantabot.domain.asta.sentiment import SentimentWeights, aged_confidence
from fantabot.domain.lineup.presence import PresenceWeights, cal
from fantabot.domain.shared.values import SentimentRow

#: The three states `FANTABOT_LINEUP_SENTIMENT` can be in.
OFF = "off"
SHADOW = "shadow"
LIVE = "live"
SENTIMENT_MODES: tuple[str, ...] = (OFF, SHADOW, LIVE)

#: Reused, not restated: both this and `presence.py` trust one reading's age alike.
HALF_LIFE_DAYS: float = SentimentWeights().half_life_days
#: `presence.py`'s own P(vote | available, not starting) prior, per Classic role.
Q_ROLE: Mapping[str, float] = PresenceWeights().q_role


def parse_sentiment_mode(raw: str | None) -> str:
    """`FANTABOT_LINEUP_SENTIMENT` as a mode, failing closed to `off` (AD4).

    `Settings()` runs at import, so a typo in `.env` must not stop the hourly job at the
    import line — it must plan the lineup exactly as it did before this feature existed.
    """
    candidate = (raw or "").strip().lower()
    return candidate if candidate in SENTIMENT_MODES else OFF


def adjusted_p_play(
    p_play: float,
    row: SentimentRow,
    *,
    pid: int,
    role: str,
    as_of: date,
) -> tuple[float, float]:
    """`p_play`, nudged by one news reading. Returns `(new_p_play, news_weight)`.

    `news_weight` is the reading's aged confidence — 0 for a silent or ancient row, in which
    case `new_p_play == p_play` exactly. Carried back so the caller can record how much this
    player's number actually moved, for the shadow-mode summary and `plan --explain`.
    """
    if row.player_id != str(pid):
        raise ValueError(f"the reading for player {pid} is player {row.player_id!r}'s")
    weights = SentimentWeights(half_life_days=HALF_LIFE_DAYS)
    w = aged_confidence(row, as_of=as_of, weights=weights)
    d_eff = 1.0 - w * (1.0 - row.disponibilita)
    tv = cal(row.titolarita, d=row.disponibilita, q=Q_ROLE[role])
    return (1.0 - w) * d_eff * p_play + w * tv, w


def top_movers(
    baseline: Mapping[int, float], adjusted: Mapping[int, float], *, limit: int = 5
) -> list[tuple[int, float, float]]:
    """`(pid, old_score, new_score)` for the players sentiment would move most, largest
    absolute change first. Pure presentation data — the shadow-mode warning's source, not a
    decision: nothing here chooses whether the change is applied.
    """
    changed = [
        (pid, baseline[pid], adjusted[pid])
        for pid in baseline
        if pid in adjusted and adjusted[pid] != baseline[pid]
    ]
    changed.sort(key=lambda t: abs(t[2] - t[1]), reverse=True)
    return changed[:limit]


__all__ = [
    "HALF_LIFE_DAYS",
    "LIVE",
    "OFF",
    "Q_ROLE",
    "SENTIMENT_MODES",
    "SHADOW",
    "adjusted_p_play",
    "parse_sentiment_mode",
    "top_movers",
]
