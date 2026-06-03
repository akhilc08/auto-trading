---
phase: 02-flights
plan: 03
type: execute
wave: 3
depends_on: ["02-02"]
files_modified:
  - flights/exec/exec_macro_vol.py
  - flights/exec/exec_trend_following.py
autonomous: false
requirements: [EXEC-02, EXEC-03, EXEC-04, EXEC-05, EXEC-06, EXEC-07, EXEC-08, SECRETS-02, SECRETS-03]
user_setup:
  - service: alpaca
    why: "macro_vol and trend_following Alpaca paper credentials, stored as MotherDuck secrets in plan 02-01"
    env_vars:
      - name: MOTHERDUCK_TOKEN
        source: "MotherDuck Settings -> Service Accounts (service account token)"
must_haves:
  truths:
    - "A Flight named exec-macro-vol runs the macro_vol account strategy (vol_risk_premium) on MotherDuck compute"
    - "A Flight named exec-trend-following runs the nine trend_following account strategies on MotherDuck compute"
    - "Each Flight reads only its own account's Alpaca secret and writes trades/positions/portfolio_snapshots"
    - "Each Flight exits cleanly with no orders when the market is closed"
  artifacts:
    - path: "flights/exec/exec_macro_vol.py"
      provides: "exec-macro-vol Flight entrypoint"
      contains: "def main"
    - path: "flights/exec/exec_trend_following.py"
      provides: "exec-trend-following Flight entrypoint"
      contains: "def main"
  key_links:
    - from: "flights/exec/exec_macro_vol.py"
      to: "flights/exec/_runner.run_account_flight"
      via: "scaffold reuse with account macro_vol, secret alpaca_macro_vol"
      pattern: "run_account_flight"
    - from: "flights/exec/exec_trend_following.py"
      to: "flights/exec/_runner.run_account_flight"
      via: "scaffold reuse with account trend_following, secret alpaca_trend_following"
      pattern: "run_account_flight"
---

<objective>
Add the remaining two execution Flights using the reusable scaffold built in plan 02-02:
`exec-macro-vol` (runs vol_risk_premium for the macro_vol account) and `exec-trend-following`
(runs the nine trend_following-account strategies: trend_following, trend_following_v2,
multi_factor_equity, multi_factor_equity_v2, regime_switching, post_earnings_drift, rl_alpha,
deep_learning, alt_data_fusion). Each is a thin entrypoint calling
`run_account_flight(account, strategy_names, secret_name)` and is deployed as its own Flight,
reading only its account's secret.

Purpose: Complete the move of all strategy execution onto MotherDuck Flights (phase goal),
covering the two accounts not handled in plan 02-02.
Output: Two thin Flight entrypoints + two live Flights (exec-macro-vol, exec-trend-following).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/research/ARCHITECTURE.md
@.planning/research/STACK.md
@.planning/phases/02-flights/02-02-exec-flight-stat-arb-PLAN.md
@.planning/phases/02-flights/02-02-SUMMARY.md
@flights/exec/_runner.py
@flights/exec/_logger.py
@strategies/vol_risk_premium/config.py
@strategies/trend_following/config.py
</context>

<design_notes>
- **Reuse, do not rebuild:** both entrypoints call the exact `run_account_flight` signature
  from plan 02-02. No new scaffold or logger logic. If 02-02's SUMMARY records a different
  signature than `run_account_flight(account_name, strategy_names, secret_name)`, match the
  shipped signature.
- **EXEC-02 grouping:** account `macro_vol` = [vol_risk_premium]; secret `alpaca_macro_vol`.
- **EXEC-03 grouping (authoritative for this phase):** account `trend_following` =
  [trend_following, trend_following_v2, multi_factor_equity, multi_factor_equity_v2,
  regime_switching, post_earnings_drift, rl_alpha, deep_learning, alt_data_fusion]; secret
  `alpaca_trend_following`. NOTE: this differs from `core/accounts.py` (which splits these
  across macro_vol/stock_alpha). The Flights phase follows the EXEC requirement groupings and
  bundles its own strategy lists; do NOT import or modify `core/accounts.py`.
- **Scheduling (EXEC-06):** all strategies daily; reuse the post-close cron from plan 02-02
  (`"5 20 * * 1-5"` summer / `"5 21 * * 1-5"` winter). All three execution Flights share the
  same daily-after-close schedule.
- **Market guard / Alpaca / writes (EXEC-04/05/07):** inherited from `_runner.py` — no
  per-Flight reimplementation.
</design_notes>

<artifacts_this_phase_produces>
This plan creates:
- **Flights (live, in MotherDuck):** `exec-macro-vol`, `exec-trend-following`
- **Files:** `flights/exec/exec_macro_vol.py`, `flights/exec/exec_trend_following.py`
- **Functions:** `exec_macro_vol.main()`, `exec_trend_following.main()`
- **Secrets consumed:** `alpaca_macro_vol`, `alpaca_trend_following`
</artifacts_this_phase_produces>

<phase1_dependency_note>
Same as plan 02-02: assumes the Phase 1 tables and write contracts exist. The shared
`_logger.py` (from plan 02-02) already targets the Phase 1 schema; these entrypoints add no new
schema assumptions.
</phase1_dependency_note>

<tasks>

<task type="auto">
  <name>Task 1: exec-macro-vol and exec-trend-following entrypoints</name>
  <files>flights/exec/exec_macro_vol.py, flights/exec/exec_trend_following.py</files>
  <read_first>
    - flights/exec/_runner.py (run_account_flight signature)
    - flights/exec/exec_stat_arb.py (entrypoint pattern to mirror exactly)
    - .planning/phases/02-flights/02-02-SUMMARY.md (confirmed signature + cron)
    - .planning/REQUIREMENTS.md (EXEC-02, EXEC-03)
    - strategies/vol_risk_premium/config.py, strategies/trend_following/config.py (confirm strategy folder names)
  </read_first>
  <action>
    Create `flights/exec/exec_macro_vol.py` with `def main():` calling
    `run_account_flight("macro_vol", ["vol_risk_premium"], "alpaca_macro_vol")`. Create
    `flights/exec/exec_trend_following.py` with `def main():` calling
    `run_account_flight("trend_following", ["trend_following","trend_following_v2",
    "multi_factor_equity","multi_factor_equity_v2","regime_switching","post_earnings_drift",
    "rl_alpha","deep_learning","alt_data_fusion"], "alpaca_trend_following")`. Import
    `run_account_flight` from the bundled `_runner` exactly as `exec_stat_arb.py` does. No other
    logic. Do NOT modify any strategy or core file.
  </action>
  <verify>
    <automated>python -c "import ast; mv=open('flights/exec/exec_macro_vol.py').read(); tf=open('flights/exec/exec_trend_following.py').read(); assert 'def main' in mv and 'def main' in tf; assert 'run_account_flight' in mv and 'run_account_flight' in tf; assert 'macro_vol' in mv and 'alpaca_macro_vol' in mv and 'vol_risk_premium' in mv; assert 'trend_following' in tf and 'alpaca_trend_following' in tf; need=['trend_following','trend_following_v2','multi_factor_equity','multi_factor_equity_v2','regime_switching','post_earnings_drift','rl_alpha','deep_learning','alt_data_fusion']; missing=[s for s in need if s not in tf]; assert not missing, missing; print('PASS')"</automated>
  </verify>
  <acceptance_criteria>
    - `exec_macro_vol.main()` calls `run_account_flight` with account `macro_vol`, strategy list `[vol_risk_premium]`, secret `alpaca_macro_vol` (EXEC-02, SECRETS-03).
    - `exec_trend_following.main()` calls `run_account_flight` with account `trend_following`, ALL nine EXEC-03 strategy names, secret `alpaca_trend_following` (EXEC-03, SECRETS-03).
    - Both import `run_account_flight` from the bundled `_runner` (no reimplemented scaffold).
    - No file under `strategies/` or `core/` is modified.
  </acceptance_criteria>
  <done>Both entrypoints exist and reuse the scaffold with correct per-account strategy lists and secrets.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking-human">
  <name>Task 2: Deploy and verify exec-macro-vol and exec-trend-following end-to-end</name>
  <read_first>
    - flights/exec/exec_macro_vol.py, flights/exec/exec_trend_following.py
    - flights/exec/_runner.py, flights/exec/_logger.py, flights/exec/requirements.txt
    - .planning/phases/02-flights/02-01-SUMMARY.md (secrets), 02-02-SUMMARY.md (deploy pattern + cron)
    - .planning/REQUIREMENTS.md (Phase 2 success criteria 2 and 3)
  </read_first>
  <what-built>
    Two Flights deployed via the MotherDuck Flight mechanism using the same bundle/requirements/
    access_token_name/cron pattern as `exec-stat-arb` (plan 02-02):
    - `exec-macro-vol` (source: exec_macro_vol.py)
    - `exec-trend-following` (source: exec_trend_following.py)
  </what-built>
  <how-to-verify>
    1. Trigger `exec-macro-vol` during market hours. Confirm trades/positions/portfolio_snapshots
       rows with account_name='macro_vol' and strategy_name='vol_risk_premium'.
    2. Trigger `exec-trend-following` during market hours. Confirm rows with
       account_name='trend_following' and strategy_name across the nine EXEC-03 strategies
       (some strategies may legitimately place no order on a given day — confirm at least the
       portfolio_snapshots row appears for the account and no error occurs).
    3. Trigger each Flight when the market is CLOSED. Confirm the "market closed — exiting"
       log and zero new trades rows (Phase 2 success criterion 3).
    4. Confirm exec-macro-vol reads only alpaca_macro_vol and exec-trend-following reads only
       alpaca_trend_following; no Alpaca key appears in any Flight source/config/log.
  </how-to-verify>
  <acceptance_criteria>
    - Both Flights exist in MotherDuck with the shared post-close cron and access_token_name set.
    - Market-hours runs produce rows tagged with the correct account_name for each Flight.
    - Market-closed runs log the closed message and add zero trades rows.
    - Each Flight reads only its own account secret; no plaintext credential in source/config/logs.
  </acceptance_criteria>
  <resume-signal>Type "approved" once both Flights wrote rows during market hours and exited cleanly when closed, or describe failures.</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MotherDuck secret store → each Flight | each Flight reads only its account's Alpaca credentials |
| Flight → Alpaca API | order submission per account |
| Flight → MotherDuck tables | trade/position writes |
| repo (git) → public | no plaintext credentials in Flight source |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-03-01 | Elevation of Privilege | A Flight reads another account's Alpaca secret | mitigate | exec_macro_vol passes only `alpaca_macro_vol`; exec_trend_following passes only `alpaca_trend_following`; per-account scope (SECRETS-03); Task 2 verifies |
| T-02-03-02 | Information Disclosure | Alpaca keys leak into Flight source/config/logs | mitigate | Inherited from _runner.py: keys read from secret at runtime, never logged; Task 2 confirms no key in source/config/logs (SECRETS-02) |
| T-02-03-03 | Tampering | Duplicate trade rows on re-run | mitigate | Inherited `log_order` `ON CONFLICT (order_id) DO NOTHING` |
| T-02-03-04 | Denial of Service | Flight trades when market closed | mitigate | Inherited `get_clock().is_open` guard (EXEC-07); Task 2 verifies zero orders when closed |
| T-02-03-SC | Tampering | pip installs in Flight | mitigate | Reuses plan 02-02 `requirements.txt` (duckdb==1.5.2 + alpaca-py); no new packages introduced |
</threat_model>

<verification>
- exec_macro_vol.main() and exec_trend_following.main() reuse run_account_flight with correct account/strategy/secret args (EXEC-02, EXEC-03, SECRETS-03).
- All nine EXEC-03 strategy names present in exec_trend_following.py.
- Live: both Flights write rows during market hours and exit cleanly when closed (Task 2 checkpoint).
- No strategy/core file modified.
</verification>

<success_criteria>
- exec-macro-vol runs vol_risk_premium on MotherDuck compute (EXEC-02).
- exec-trend-following runs the nine trend_following strategies on MotherDuck compute (EXEC-03).
- Each reads only its account secret and writes the three tables (EXEC-04/05, SECRETS-02/03).
- Scheduled post-close (EXEC-06); exits cleanly when closed (EXEC-07); duckdb==1.5.2 pinned (EXEC-08, inherited).
</success_criteria>

<output>
Create `.planning/phases/02-flights/02-03-SUMMARY.md` when done. Record both deployed Flight
names and their crons.
</output>
