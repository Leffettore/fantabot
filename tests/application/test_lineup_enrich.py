"""`enrich`/`load_predictions` — the Classic extras, and `FANTABOT_LINEUP_SENTIMENT`'s three
modes. No database: `LineupHistoryRepository` is monkeypatched at its import site, the same
seam that keeps the hourly `indexcompare` submit from loading persistence at all.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from fantabot.application.lineup_enrich import enrich, load_predictions
from fantabot.application.lineup_planner import LineupInputs
from fantabot.domain.shared.values import SentimentRow

AS_OF = date(2026, 9, 20)

ROW = {"pid": 1, "role": [3], "percent": 80.0, "status": 1, "plyr": "Testman"}


class _FakeRepo:
    """The five reads `load_predictions` makes, none of them touching a real session."""

    def __init__(self, _session: object = None) -> None:
        self.season: str | None = None
        self.sentiment: dict[int, SentimentRow] = {}
        self.latest_sentiment_calls = 0
        self.forbid_latest_sentiment = False

    def latest_season(self) -> str | None:
        return self.season

    def prior_fantamedia(self, ids: Any, season: str) -> dict[int, float]:
        return {}

    def prior_media_voto(self, ids: Any, season: str) -> dict[int, float]:
        return {}

    def past_clubs(self, ids: Any, season: str) -> dict[int, frozenset[str]]:
        return {}

    def fixture_scores(self, season: str) -> list[Any]:
        return []

    def latest_sentiment(self, ids: Any) -> dict[int, SentimentRow]:
        if self.forbid_latest_sentiment:
            raise AssertionError("latest_sentiment must not be called")
        self.latest_sentiment_calls += 1
        return self.sentiment


def _reading(
    player_id: str, *, disponibilita: float, titolarita: float, confidenza: float = 1.0
) -> SentimentRow:
    return SentimentRow(
        player_id=player_id, nome=f"p{player_id}", data_run="2026-09-20", sentiment=0.0,
        disponibilita=disponibilita, titolarita=titolarita, mercato=0.0, forma=0.0,
        rigorista=0.0, piazzati=0.0, confidenza=confidenza, ruolo_campo="",
        ruoli_mantra="", deriva_ruolo=0.0,
    )


@pytest.fixture
def fake_repo(monkeypatch: pytest.MonkeyPatch) -> _FakeRepo:
    repo = _FakeRepo()
    monkeypatch.setattr(
        "fantabot.adapters.persistence.repositories.lineup_history.LineupHistoryRepository",
        lambda session: repo,
    )
    return repo


class TestLoadPredictionsOff:
    def test_no_as_of_never_calls_latest_sentiment_even_with_a_reading_pending(
        self, fake_repo: _FakeRepo
    ) -> None:
        fake_repo.forbid_latest_sentiment = True
        preds = load_predictions(object(), [ROW], cmday=6)  # type: ignore[arg-type]
        assert preds[1].factors["news_weight"] == 0.0

    def test_explicit_off_never_calls_latest_sentiment(
        self, fake_repo: _FakeRepo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FANTABOT_LINEUP_SENTIMENT", "off")
        fake_repo.forbid_latest_sentiment = True
        preds = load_predictions(object(), [ROW], cmday=6, as_of=AS_OF)  # type: ignore[arg-type]
        assert preds[1].factors["news_weight"] == 0.0

    def test_an_empty_feed_falls_back_to_the_plain_predictor(
        self, fake_repo: _FakeRepo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FANTABOT_LINEUP_SENTIMENT", "shadow")
        preds = load_predictions(object(), [ROW], cmday=6, as_of=AS_OF)  # type: ignore[arg-type]
        assert fake_repo.latest_sentiment_calls == 1
        assert preds[1].factors["news_weight"] == 0.0


class TestLoadPredictionsShadow:
    def test_the_ranking_is_the_baseline_s_untouched(
        self, fake_repo: _FakeRepo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FANTABOT_LINEUP_SENTIMENT", "shadow")
        fake_repo.sentiment = {1: _reading("1", disponibilita=0.0, titolarita=0.0)}

        baseline = load_predictions(object(), [ROW], cmday=6)  # type: ignore[arg-type]
        shadow = load_predictions(object(), [ROW], cmday=6, as_of=AS_OF)  # type: ignore[arg-type]

        assert shadow[1].p_play == pytest.approx(baseline[1].p_play)
        assert shadow[1].score == pytest.approx(baseline[1].score)

    def test_the_shadow_score_and_news_weight_are_attached(
        self, fake_repo: _FakeRepo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FANTABOT_LINEUP_SENTIMENT", "shadow")
        fake_repo.sentiment = {1: _reading("1", disponibilita=0.0, titolarita=0.0)}

        preds = load_predictions(object(), [ROW], cmday=6, as_of=AS_OF)  # type: ignore[arg-type]

        assert preds[1].factors["news_weight"] == pytest.approx(1.0)
        assert preds[1].factors["shadow_score"] == pytest.approx(0.0)
        assert preds[1].score != pytest.approx(0.0)

    def test_a_mover_calls_warn_with_a_readable_summary(
        self, fake_repo: _FakeRepo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FANTABOT_LINEUP_SENTIMENT", "shadow")
        fake_repo.sentiment = {1: _reading("1", disponibilita=0.0, titolarita=0.0)}
        seen: list[str] = []

        load_predictions(
            object(), [ROW], cmday=6, as_of=AS_OF, warn=seen.append  # type: ignore[arg-type]
        )

        assert len(seen) == 1
        assert "Testman" in seen[0]
        assert "shadow" in seen[0]

    def test_nothing_moving_calls_warn_zero_times(
        self, fake_repo: _FakeRepo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A silent reading (`confidenza` 0) has weight 0, so `adjusted_p_play` is a no-op —
        the one case guaranteed to move nothing, whatever `disponibilita`/`titolarita` say."""
        monkeypatch.setenv("FANTABOT_LINEUP_SENTIMENT", "shadow")
        fake_repo.sentiment = {
            1: _reading("1", disponibilita=0.0, titolarita=0.0, confidenza=0.0)
        }
        seen: list[str] = []

        load_predictions(
            object(), [ROW], cmday=6, as_of=AS_OF, warn=seen.append  # type: ignore[arg-type]
        )

        assert seen == []


class TestLoadPredictionsLive:
    def test_the_adjusted_predictions_rank(
        self, fake_repo: _FakeRepo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FANTABOT_LINEUP_SENTIMENT", "live")
        fake_repo.sentiment = {1: _reading("1", disponibilita=0.0, titolarita=0.0)}

        preds = load_predictions(object(), [ROW], cmday=6, as_of=AS_OF)  # type: ignore[arg-type]

        assert preds[1].p_play == pytest.approx(0.0)
        assert preds[1].score == pytest.approx(0.0)


class TestEnrichMantraUnaffected:
    def test_a_mantra_lega_never_reaches_load_predictions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`FANTABOT_LINEUP_SENTIMENT` set to `live` must still not move a Mantra plan —
        `enrich`'s format guard fires before `load_predictions` is even called."""
        monkeypatch.setenv("FANTABOT_LINEUP_SENTIMENT", "live")

        def _boom(*_a: object, **_k: object) -> object:
            raise AssertionError("load_predictions must not run for a Mantra lega")

        monkeypatch.setattr("fantabot.application.lineup_enrich.load_predictions", _boom)

        inputs = LineupInputs(
            roster_ids=(1,), roles_by_id={1: ("P",)}, fvmma_by_id={1: 5.0}, modules=(),
            competition=1, mday=1, cmday=1, tid=1, bench_size=0, fmt="mantra",
        )
        out = enrich(
            inputs, object(), 1, [ROW], session=object()  # type: ignore[arg-type]
        )
        assert out is inputs
