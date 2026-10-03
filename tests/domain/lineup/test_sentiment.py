"""The lineup's own news nudge: `p_play`, moved by one reading. Pure."""

from __future__ import annotations

from datetime import date

import _importgraph as G
import pytest

from fantabot.domain.lineup.presence import cal
from fantabot.domain.lineup.sentiment import (
    LIVE,
    OFF,
    SHADOW,
    adjusted_p_play,
    parse_sentiment_mode,
    top_movers,
)
from fantabot.domain.shared.values import SentimentRow

AS_OF = date(2026, 9, 20)


def _reading(
    player_id: str = "7",
    *,
    run: str = "2026-09-20",
    disponibilita: float = 1.0,
    titolarita: float = 1.0,
    confidenza: float = 1.0,
) -> SentimentRow:
    return SentimentRow(
        player_id=player_id, nome=f"p{player_id}", data_run=run, sentiment=0.0,
        disponibilita=disponibilita, titolarita=titolarita, mercato=0.0, forma=0.0,
        rigorista=0.0, piazzati=0.0, confidenza=confidenza, ruolo_campo="",
        ruoli_mantra="", deriva_ruolo=0.0,
    )


class TestParseSentimentMode:
    @pytest.mark.parametrize("mode", [OFF, SHADOW, LIVE])
    def test_a_known_mode_round_trips(self, mode: str) -> None:
        assert parse_sentiment_mode(mode) == mode

    @pytest.mark.parametrize("mode", [SHADOW, LIVE])
    def test_case_and_whitespace_are_ignored(self, mode: str) -> None:
        assert parse_sentiment_mode(f"  {mode.upper()}  ") == mode

    @pytest.mark.parametrize("raw", [None, "", "on", "true", "projection"])
    def test_anything_unknown_fails_closed_to_off(self, raw: str | None) -> None:
        assert parse_sentiment_mode(raw) == OFF


class TestAdjustedPPlay:
    def test_a_silent_reading_leaves_p_play_untouched(self) -> None:
        silent = _reading(disponibilita=0.0, titolarita=0.0, confidenza=0.0)
        new_p, w = adjusted_p_play(0.8, silent, pid=7, role="C", as_of=AS_OF)
        assert new_p == pytest.approx(0.8)
        assert w == 0.0

    def test_a_fresh_certain_reading_is_the_vote_scale_alone(self) -> None:
        """w = 1, so p_play's own value is fully replaced by cal()'s."""
        reading = _reading(disponibilita=1.0, titolarita=0.3, confidenza=1.0)
        new_p, w = adjusted_p_play(0.9, reading, pid=7, role="C", as_of=AS_OF)
        assert w == pytest.approx(1.0)
        assert new_p == pytest.approx(cal(0.3, d=1.0, q=0.55))

    def test_a_fresh_certain_injury_zeroes_the_probability(self) -> None:
        injured = _reading(disponibilita=0.0, titolarita=0.0, confidenza=1.0)
        new_p, _w = adjusted_p_play(0.9, injured, pid=7, role="A", as_of=AS_OF)
        assert new_p == pytest.approx(0.0)

    def test_a_week_old_injury_counts_half(self) -> None:
        injured = _reading(run="2026-09-13", disponibilita=0.0, titolarita=0.0)
        new_p, w = adjusted_p_play(0.8, injured, pid=7, role="C", as_of=AS_OF)
        assert w == pytest.approx(0.5)
        assert new_p == pytest.approx(0.25 * 0.8)

    def test_a_stale_injury_decays_back_to_p_play(self) -> None:
        injured = _reading(run="2026-07-12", disponibilita=0.0, titolarita=0.0)
        new_p, _w = adjusted_p_play(0.8, injured, pid=7, role="C", as_of=AS_OF)
        assert new_p == pytest.approx(0.8, abs=2e-3)
        assert new_p < 0.8

    def test_a_reading_filed_under_another_id_is_refused(self) -> None:
        with pytest.raises(ValueError, match="8"):
            adjusted_p_play(0.8, _reading("8"), pid=7, role="C", as_of=AS_OF)

    def test_each_role_uses_its_own_bench_rate(self) -> None:
        reading = _reading(titolarita=0.0, disponibilita=1.0, confidenza=1.0)
        new_p, _w = adjusted_p_play(0.9, reading, pid=7, role="P", as_of=AS_OF)
        assert new_p == pytest.approx(0.15)

    def test_an_unknown_role_is_refused(self) -> None:
        reading = _reading()
        with pytest.raises(KeyError):
            adjusted_p_play(0.8, reading, pid=7, role="M", as_of=AS_OF)


class TestTopMovers:
    def test_the_largest_absolute_change_comes_first(self) -> None:
        baseline = {1: 5.0, 2: 5.0, 3: 5.0}
        adjusted = {1: 5.5, 2: 3.0, 3: 5.0}
        assert top_movers(baseline, adjusted) == [(2, 5.0, 3.0), (1, 5.0, 5.5)]

    def test_an_unchanged_player_is_left_out(self) -> None:
        assert top_movers({1: 5.0}, {1: 5.0}) == []

    def test_a_player_missing_from_either_side_is_left_out(self) -> None:
        assert top_movers({1: 5.0, 2: 5.0}, {1: 6.0}) == [(1, 5.0, 6.0)]

    def test_the_limit_is_respected(self) -> None:
        baseline = {i: 5.0 for i in range(10)}
        adjusted = {i: 5.0 + i for i in range(10)}
        assert len(top_movers(baseline, adjusted, limit=3)) == 3

    def test_no_movement_at_all_is_an_empty_list(self) -> None:
        assert top_movers({}, {}) == []


def test_sentiment_reads_no_clock() -> None:
    clock_reads = {"now", "today", "utcnow", "time", "monotonic", "perf_counter"}
    assert clock_reads & G.names_used("fantabot.domain.lineup.sentiment") == set()
