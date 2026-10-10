"""Where each test file lives, and why that is a table rather than a rule.

`tests/` mirrors `src/fantabot/`: a test sits in the layer of the thing it is about. Two
mechanical ways to derive that were tried and both are wrong often enough to mislead,
which is worse than not mirroring at all -- a misfiled test tells a reader the module is
in a layer it is not.

* **Voting on the file's imports** puts `test_token_store.py` in `domain/` because the
  store's tests build claims, ciphers and errors around one adapter call.
* **Matching the filename to a module leaf** puts `test_state.py` under `domain/asta/`
  (there is a `state.py` there) when it is about `adapters/browser/storage_state.py`, and
  `test_apileague_client.py` under the harvest client.

So the subject of each file is written down. The entries that are not obvious carry the
reason; the rest are their own explanation.

`tests/` deliberately has no `__init__.py`, here or in any subdirectory. pytest derives a
module name from the path relative to rootdir, and the suite's helpers (`_paths`,
`_golden`, `_importgraph`) are imported by bare name, which works because `conftest.py`
puts `tests/` on `sys.path`. Adding `__init__.py` would change both and is not needed:
no two test files share a basename, which `test_testtree.py` checks.
"""

from __future__ import annotations

#: file -> directory under `tests/`. The subject's layer, then its feature.
TREE: dict[str, str] = {
    # -- domain/asta: the decision logic ------------------------------------------------
    "test_asta_legality.py": "domain/asta",
    "test_asta_sentiment.py": "domain/asta",
    "test_roster.py": "domain/lineup",
    # -- domain/lega: the platform's own JSON, translated
    "test_lega_parse.py": "domain/lega",
    "test_schema.py": "domain/lineup",
    "test_positional.py": "domain/lineup",
    # About the default lineup path's imports and `domain/lineup`'s randomness, though it
    # reads the graph from `interface/` down: the claim is about the lineup, not a layer.
    "test_lineup_imports.py": "domain/lineup",
    "test_value.py": "domain/lineup",
    "test_scoring.py": "domain/lineup",
    "test_scoring_reconcile.py": "domain/lineup",
    "test_history.py": "domain/lineup",
    "test_projection.py": "domain/lineup",
    "test_presence.py": "domain/lineup",
    "test_dependence.py": "domain/lineup",
    "test_freshness.py": "domain/lineup",
    "test_backtest.py": "domain/lineup",
    "test_gate_statistic.py": "domain/lineup",
    "test_bench_mc.py": "domain/lineup",
    "test_choose.py": "domain/lineup",
    "test_simulate.py": "domain/lineup",
    "test_substitution.py": "domain/lineup",
    # The engine replayed against the platform's own substitutions, so the subject is
    # `domain/lineup/substitution.py` even though every input is a saved HTTP response.
    "test_substitution_reconcile.py": "domain/lineup",
    "test_backtest_corpus.py": "domain/lineup",
    "test_opponent.py": "domain/lineup",
    "test_candidates.py": "domain/lineup",
    "test_build.py": "domain/lineup",
    "test_bench.py": "domain/lineup",
    "test_marle.py": "domain/lineup",
    "test_competition.py": "domain/lineup",
    "test_payload.py": "domain/lineup",
    "test_deadline.py": "domain/lineup",
    "test_predict.py": "domain/lineup",
    "test_extras.py": "domain/lineup",
    "test_activity.py": "domain/lineup",
    "test_defence.py": "domain/lineup",
    "test_rules.py": "domain/lineup",
    # The rule is about the whole asta feature including its command, but what it
    # protects -- one calendar seam for the golden harness -- is a property of the
    # decision layer, which is the half that must be deterministic.
    # `ruolo_campo` must never reach a decision module. That is a domain rule about
    # domain modules, checked over the domain package.
    # -- domain/harvest ------------------------------------------------------------------
    "test_aste_models.py": "domain/harvest",
    "test_aste_fixtures.py": "domain/harvest",
    # `compare.py` is the domain module; the `scripts/` file of nearly the same name was
    # deleted in W2, and the two were conflated once already.
    # Review fixes across the reducer and reconstruct; the subject is the fold.
    # -- domain/news ----------------------------------------------------------------------
    "test_news_mantra.py": "domain/news",
    "test_news_models.py": "domain/news",
    "test_news_prompt.py": "domain/news",
    "test_news_pool.py": "domain/news",
    "test_news_sink.py": "domain/news",
    "test_news_store.py": "domain/news",
    "test_news_store_contract.py": "domain/news",
    "test_news_cost_report.py": "domain/news",
    # -- domain/classic: the Classic (P/D/C/A) engine -------------------------------------
    "test_classic_roles.py": "domain/classic",
    "test_classic_formations.py": "domain/classic",
    "test_classic_lineup.py": "domain/classic",
    "test_classic_lineup_planner.py": "domain/classic",
    # -- domain/mantra, domain/shared, domain/tokens --------------------------------------
    "test_club_names.py": "domain/shared",
    "test_league.py": "domain/shared",
    "test_parsing.py": "domain/shared",
    "test_resources.py": "domain/shared",
    "test_token_capture.py": "domain/tokens",
    "test_token_claims.py": "domain/tokens",
    "test_token_crypto.py": "domain/tokens",
    "test_token_status.py": "domain/tokens",
    # -- application ----------------------------------------------------------------------
    "test_lineup_planner.py": "application",
    # The capture loop that replaced "press Enter once you are logged in".
    "test_login_wait.py": "application",
    "test_lega_sync.py": "application",
    # T19: which listone a room is priced against, and who said so. Pure — the rungs are
    # decided here and fetched in `interface/asta.py`.
    # The credit walk-away. Filed by its subject: it is the number a bid is made against,
    # and `application/` is where the pair that computes it is assembled.
    "test_arming.py": "application",
    # T28: `safe_dsn` and the secret sets — the two decisions `config-check` and the
    # app's System page must not each keep a copy of.
    # T24: what a valid exclusion is, and what a row with no name means — the two
    # decisions `db exclude`/`db exclusions` and the Asta page share.
    # T25: the two one-shot team commands — which endpoint `snapshot-team` reads, and
    # what an untrustworthy club-name mapping means to the command that is its remedy.
    # T23: what `db scrape` may be asked for — the three tables, what a season is, and
    # the `DEFAULT_SEASONS` staleness report (the two short lists are fixed; the report
    # is kept for the next August and driven by shortening a scraper's own list).
    # T26: where a dump lands, and the refusal that keeps it off this volume. Separate
    # from `test_cli_db_dump.py`, which is about the CLI's printing of it.
    "test_lineup_submit.py": "application",
    "test_lineup_shadow_wiring.py": "application",
    "test_lineup_shadow.py": "application",
    "test_lineup_projection.py": "application",
    "test_lineup_golden.py": "application",
    # T18-lift part 1: the composition of a live room — the twenty keywords `asta room`
    # and the app's room route must not each assemble, and the one poll both drive it
    # through. Separate from `test_asta_room_tracker.py`, which is about what one cycle
    # decides rather than about who wired the decider.
    # T22: what a backfill may be asked to load — the refusals, and the enumeration
    # of the harvest home that the picker and `harvest backfill` must not each invent.
    "test_lineup_backtest.py": "application",
    "test_lineup_refresh.py": "application",
    "test_news_roster.py": "application",
    "test_news_pipeline.py": "application",
    "test_news_pipeline_limits.py": "application",
    # -- adapters -------------------------------------------------------------------------
    "test_agentkit_env.py": "adapters/agent",
    "test_agentkit_options.py": "adapters/agent",
    "test_agentkit_runner.py": "adapters/agent",
    "test_agentkit_usage.py": "adapters/agent",
    "test_voti_range.py": "adapters/scraping",
    "test_apileague_client.py": "adapters/http",
    "test_apileague_teamlineup.py": "adapters/http",
    "test_aste_no_sockets.py": "adapters/http",
    # The claim is about the modules that collect, which now span three layers; it is
    # filed with the transport that would carry a filtered query.
    "test_lineup_runs.py": "adapters/files",
    # The process-group runner. Filed under `files` with the other small adapters that
    # touch the machine rather than the network.
    "test_process_group.py": "adapters/files",
    # The reader, beside the writer. Filed by its subject rather than its imports: it
    # reads `application/asta_room.py` to check the writer and the reader still agree.
    "test_db_boundary.py": "adapters/persistence",
    "test_db_models.py": "adapters/persistence",
    "test_upserts.py": "adapters/persistence",
    # Filed with the read it measures, not with the pure rule beside it: what it pins
    # is what is in the database, which is the repository's subject.
    "test_backtest_corpus_db.py": "adapters/persistence",
    # The gate's smoke run. Filed with the reads it crosses, which is what it is about:
    # a fake cannot prove that real ids join.
    "test_lineup_backtest_db.py": "adapters/persistence",
    "test_migrations.py": "adapters/persistence",
    "test_token_store.py": "adapters/tokens",
    "test_token_secrecy.py": "adapters/tokens",
    # About `storage_state.py`, not `domain/asta/state.py`. The filename collision with a
    # domain module is the reason a rule cannot do this.
    "test_state.py": "adapters/browser",
    "test_config_agent_model.py": "adapters",
    # config is not an adapter, but its three tests are about what the process talks to —
    # which model, which database, and now which directory holds the harvest artefacts.
    "test_config_database_url.py": "adapters",
    "test_config_harvest_dir.py": "adapters",
    "test_config_journal_path.py": "adapters",
    # -- interface --------------------------------------------------------------------------
    # Three database failures, told apart at the command that has to retry one of them.
    # About `config.harvest_dir`, but what it pins is the four *commands* that default to it.
    "test_cli_command_set.py": "interface",
    "test_cli_forget_divergence.py": "interface",
    # T23: the lift's proof — the command fetches nothing it was not asked for, and says
    # which seasons it took before it takes minutes taking them.
    "test_cli_entrypoints.py": "interface",
    "test_lineup_cli.py": "interface",
    "test_cli_login.py": "interface",
    "test_cli_token_forget.py": "interface",
    "test_cli_token_status.py": "interface",
    # -- about the repository itself, not about one layer -------------------------------------
    "test_layers.py": ".",
    "test_importgraph.py": ".",
    "test_integration_isolation.py": ".",
    "test_suite_scope.py": ".",
    "test_scripts_resolve.py": ".",
    "test_testtree.py": ".",
    "test_docs.py": ".",
    "test_links.py": ".",
    "test_lineup_enrich.py": "application",
    "test_sentiment.py": "domain/lineup",
}
