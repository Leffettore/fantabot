"""`predict` — expected fantavoto from the lineUpInfo row plus history. Pure."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from fantabot.domain.lineup.predict import (
    Prediction,
    PredictWeights,
    RowSignals,
    TeamRates,
    predict,
    previous_season,
    signals_from_row,
    team_rates,
)
from fantabot.domain.shared.values import SentimentRow

# Two real rows from lega 3677376, 2026-09-22 (tkn/img dropped).
MALEN = {
    "pid": 5585, "percent": 80, "status": 1, "hoaw": 1, "agrd": 7.1, "fagrd": 10.6,
    "indexCompare": 17.43, "plyr": "Malen", "teamH": "COM", "teamA": "ROM", "role": [4],
}
ANGUISSA = {
    "pid": 4220, "percent": 0, "status": 2, "hoaw": 0, "agrd": 5.33, "fagrd": 5.33,
    "indexCompare": 0.0, "plyr": "Zambo Anguissa", "teamH": "NAP", "teamA": "FRO", "role": [3],
}


def _sig(pid: int, role: str = "C", **kw: Any) -> RowSignals:
    base: dict[str, Any] = dict(
        pid=pid, role=role, club="AAA", opponent="BBB", home=True, percent=90.0, status=1,
        fantamedia=6.0, index_compare=0.0,
    )
    base.update(kw)
    return RowSignals(**base)


def _run(rows: list[RowSignals], **kw: Any) -> dict[int, Prediction]:
    args: dict[str, Any] = dict(cmday=6, prior_fantamedia={}, past_clubs={}, rates={})
    args.update(kw)
    return predict(rows, **args)


def test_a_live_row_reads_club_opponent_and_venue_from_hoaw() -> None:
    s = signals_from_row(MALEN)

    assert (s.role, s.club, s.opponent, s.home) == ("A", "ROM", "COM", False)
    assert s.percent == 80 and s.fantamedia == 10.6 and s.index_compare == 17.43


def test_an_injured_player_is_expected_to_score_nothing() -> None:
    preds = _run([signals_from_row(ANGUISSA), signals_from_row(MALEN)])

    assert preds[4220].p_play == 0.0
    assert preds[4220].score == 0.0
    assert preds[5585].score > 0


def test_a_missing_percent_is_not_read_as_injured() -> None:
    preds = _run([_sig(1, percent=None)])

    assert preds[1].p_play == PredictWeights().default_percent


def test_a_flagged_status_halves_the_play_probability() -> None:
    preds = _run([_sig(1, percent=80.0, status=2)])

    assert preds[1].p_play == pytest.approx(0.4)


def test_the_prior_dominates_early_and_fades_with_games() -> None:
    row = [_sig(1, fantamedia=10.0)]
    early = _run(row, cmday=2, prior_fantamedia={1: 6.0})[1].factors["baseline"]
    late = _run(row, cmday=30, prior_fantamedia={1: 6.0})[1].factors["baseline"]

    assert 6.0 < early < late < 10.0


def test_no_graded_game_falls_back_to_the_prior_alone() -> None:
    preds = _run([_sig(1, fantamedia=0.0)], prior_fantamedia={1: 6.4})

    assert preds[1].factors["baseline"] == pytest.approx(6.4)


def test_a_leaky_opponent_helps_attackers_and_a_blunt_one_helps_defenders() -> None:
    rates = {"BBB": TeamRates(attack=0.6, defence_leak=1.6)}
    preds = _run([_sig(1, role="A"), _sig(2, role="D")], rates=rates)

    assert preds[1].factors["opponent"] > 1.0
    assert preds[2].factors["opponent"] > 1.0


def test_the_opponent_factor_is_clipped() -> None:
    rates = {"BBB": TeamRates(attack=1.0, defence_leak=10.0)}
    preds = _run([_sig(1, role="A")], rates=rates)

    assert preds[1].factors["opponent"] == PredictWeights().opp_clip[1]


def test_an_unknown_opponent_is_neutral() -> None:
    preds = _run([_sig(1, opponent="PROMOTED")], rates={"BBB": TeamRates(2.0, 2.0)})

    assert preds[1].factors["opponent"] == 1.0


def test_facing_an_ex_club_is_a_small_bump() -> None:
    preds = _run([_sig(1), _sig(2)], past_clubs={1: frozenset({"BBB"})})

    assert preds[1].factors["ex_team"] == PredictWeights().ex_team
    assert preds[2].factors["ex_team"] == 1.0


def test_index_compare_is_rescaled_and_blended() -> None:
    # Same model forecast, different indexCompare: the blend must separate them.
    preds = _run([_sig(1, index_compare=4.0), _sig(2, index_compare=16.0)])

    assert preds[2].score > preds[1].score
    assert preds[1].expected == pytest.approx(preds[2].expected)


def test_team_rates_are_relative_to_the_league_mean() -> None:
    rates = team_rates([("AAA", "BBB", 3, 0), ("BBB", "AAA", 1, 1)])

    # AAA: 4 scored, 1 conceded in 2 games; the league mean is 1.25 goals per team-game.
    assert rates["AAA"].attack == pytest.approx(2.0 / 1.25)
    assert rates["BBB"].defence_leak == pytest.approx(2.0 / 1.25)
    assert team_rates([]) == {}


def test_previous_season() -> None:
    assert previous_season("2026/27") == "2025/26"
    assert previous_season("2000/01") == "1999/00"


def _reading(player_id: str, *, disponibilita: float, titolarita: float) -> SentimentRow:
    return SentimentRow(
        player_id=player_id, nome=f"p{player_id}", data_run="2026-09-20", sentiment=0.0,
        disponibilita=disponibilita, titolarita=titolarita, mercato=0.0, forma=0.0,
        rigorista=0.0, piazzati=0.0, confidenza=1.0, ruolo_campo="",
        ruoli_mantra="", deriva_ruolo=0.0,
    )


class TestSentiment:
    """`sentiment`/`as_of` are the ablation-by-absence pair: `None` reproduces the exact
    values `predict` produced before this feature existed."""

    def test_absent_by_default_is_a_no_op(self) -> None:
        preds = _run([_sig(1, percent=80.0)])

        assert preds[1].factors["news_weight"] == 0.0

    def test_no_as_of_leaves_p_play_untouched_even_with_a_reading(self) -> None:
        """`as_of` is what turns a reading on; the reading alone must not."""
        sentiment = {1: _reading("1", disponibilita=0.0, titolarita=0.0)}
        preds = _run([_sig(1, percent=80.0)], sentiment=sentiment)

        assert preds[1].p_play == pytest.approx(0.8)
        assert preds[1].factors["news_weight"] == 0.0

    def test_a_fresh_injury_reading_zeroes_p_play_and_the_score(self) -> None:
        sentiment = {1: _reading("1", disponibilita=0.0, titolarita=0.0)}
        preds = _run(
            [_sig(1, percent=80.0)], sentiment=sentiment, as_of=date(2026, 9, 20)
        )

        assert preds[1].p_play == pytest.approx(0.0)
        assert preds[1].expected == pytest.approx(0.0)
        assert preds[1].score == pytest.approx(0.0)
        assert preds[1].factors["news_weight"] == pytest.approx(1.0)

    def test_a_reading_for_another_player_leaves_this_one_untouched(self) -> None:
        sentiment = {2: _reading("2", disponibilita=0.0, titolarita=0.0)}
        preds = _run(
            [_sig(1, percent=80.0)], sentiment=sentiment, as_of=date(2026, 9, 20)
        )

        assert preds[1].p_play == pytest.approx(0.8)
        assert preds[1].factors["news_weight"] == 0.0

    def test_vote_if_plays_is_untouched(self) -> None:
        """Scope is availability only — quality-if-he-plays is out of bounds."""
        sentiment = {1: _reading("1", disponibilita=0.0, titolarita=0.0)}
        with_news = _run(
            [_sig(1, percent=80.0)], sentiment=sentiment, as_of=date(2026, 9, 20)
        )
        without_news = _run([_sig(1, percent=80.0)])

        assert with_news[1].vote_if_plays == pytest.approx(without_news[1].vote_if_plays)
