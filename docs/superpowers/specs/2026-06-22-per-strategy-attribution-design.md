# Per-Strategy Attribution — Design

**Date:** 2026-06-22
**Status:** Approved (design)

## Problem

Analysis of the live `trading` MotherDuck database surfaced three reporting defects:

1. **Positions and equity are identical across every strategy on an account.** The
   `trend_following` account shows the same 10 positions and same equity under all 6 of its
   strategy names; `stat_arb` shows the same under all 5.
2. **Six of twelve strategies appear in snapshots but never placed a trade** — their
   "performance" is an artifact, not real activity.
3. **`trades.pnl` is `NULL` for every row** — there is no per-trade realized P&L in the trades
   table.

### Root cause (one cause, three symptoms)

Multiple strategies share a **single Alpaca paper account** (one account per group:
`trend_following`, `stat_arb`, `macro_vol`). Alpaca reports positions and equity only at the
**account level** — it cannot attribute shares to a strategy. The execution runner
(`flights/exec/_runner.py:188-203`) therefore writes the *entire account's* positions and equity
**once per strategy name**:

- Symptom 1: the whole-account snapshot is duplicated across strategy names.
- Symptom 2: every strategy that merely *loaded* (`ran_strategies`) gets a snapshot row, even with
  zero fills.
- Symptom 3: `update_fill` is hardcoded to pass `pnl=None` (`_runner.py:184`,
  `runner.py:106`); realized P&L is instead recomputed downstream in
  `flights/aggregation/daily_pnl.py` (`_realized_metrics`, average-cost fill replay).

### Key asset

Each strategy's **orders ARE correctly attributed** in the `trades` table
(`strategy_name`, `account_name`), and `daily_pnl.py` already contains working average-cost
fill-replay accounting. That machinery is the foundation of the fix.

## Approach: synthetic-from-fills (hybrid)

Of the three reported quantities, only some are genuinely derivable per strategy from attributed
fills. We fix each at the altitude where it is true:

| Quantity | Per-strategy derivable? | Resolution |
|---|---|---|
| Positions (symbol, qty, unrealized P&L) | Yes — replay the strategy's fills, mark at current price | Synthetic per-strategy |
| Realized P&L (`trades.pnl`, `daily_pnl`) | Yes — already computed in `_realized_metrics` | Backfill `trades.pnl` |
| Equity / cash (`portfolio_snapshots`) | **No** — shared cash cannot be split without a recorded per-strategy capital allocation | Record once per **account** |

**Decisions (confirmed):**
- Per-strategy equity is dropped to **account-level** — it is not reconstructable and faking it is
  what created the identical-equity artifact. Per-strategy performance is tracked via realized +
  unrealized P&L, which ARE derivable.
- Cleanup of existing data: **rebuild derivable + dedupe** — backfill `trades.pnl`, dedupe
  `portfolio_snapshots` to one row per account, rebuild latest synthetic positions per strategy.
  Historical *unrealized* P&L is NOT fabricated (no historical marks available).

## Changes

### 1. Synthetic per-strategy positions
**Files:** `flights/exec/_runner.py`, `flights/exec/_logger.py` (and the parallel
`core/motherduck_logger.py` / `runner.py` for the persistent runner).

Replace the whole-account `get_all_positions()` snapshot with, for each strategy that has a
non-zero reconstructed position, a position book built from *that strategy's* `trades` fills,
marked to market at the current price. Reuse the signed average-cost replay from
`_realized_metrics` (factor it into a shared helper).

- Current price: from Alpaca account positions' `current_price` (already fetched) keyed by symbol,
  falling back to latest quote.
- A strategy whose net position is flat writes **no rows** → phantom strategies disappear
  naturally, with no special-casing.

### 2. Backfill `trades.pnl`
**File:** `flights/aggregation/daily_pnl.py`.

During fill replay, write each closing fill's realized P&L back to `trades.pnl` (currently left
`NULL`). The trades table then shows realized P&L per closing trade on its own, without depending
on `daily_pnl` aggregation. `update_fill`'s live `pnl=None` write stays (P&L is a replay product,
not known at fill time); the aggregation flight owns `trades.pnl`.

### 3. Account-level `portfolio_snapshots`
**Files:** `flights/exec/_runner.py`, `_logger.py`, `core/motherduck_logger.py`, `runner.py`;
readers `dives/alpha-beta.tsx`, `flights/risk/risk_monitor.py`.

Write equity/cash **once per account** instead of once per strategy. Set `strategy_name` to a
sentinel (`'_account'`) rather than a real strategy name, so the column stays NOT NULL without
implying strategy attribution.

Reader updates:
- `dives/alpha-beta.tsx`: join `daily_pnl` realized P&L to equity on **`account_name`** only
  (currently joins on `strategy_name, account_name`). `strat_ret = realized_pnl / account_equity`.
- `flights/risk/risk_monitor.py`: already takes latest equity per account; simplify now that
  there is exactly one equity row per account per snapshot.

### 4. One-time cleanup migration
**File:** new `scripts/migrate_attribution.py` (or a documented one-shot SQL block).

- Backfill `trades.pnl` for all historical fills via the same replay.
- Dedupe `portfolio_snapshots`: collapse the N-per-strategy equity rows to one `'_account'` row per
  (account, snapshot_at), preserving the real account equity curve.
- Rebuild latest synthetic positions per strategy from full fill history at latest available marks;
  drop the duplicated whole-account position rows.
- Do NOT fabricate historical unrealized P&L.

Run against a cloned/snapshot copy first; verify row counts and a spot-check strategy before
applying to `trading`.

## Testing

- Unit tests for synthetic position reconstruction: long open/add, partial close, full close,
  short open/cover, flip past flat — mirroring the existing `_realized_metrics` cases.
- Unit test for `trades.pnl` backfill: closing fills get correct realized P&L; opening fills stay
  `NULL`.
- Migration verified against a copy: post-migration `portfolio_snapshots` has one row per
  (account, snapshot_at); no strategy shows positions it never traded.

## Out of scope

- Per-strategy capital allocation / true per-strategy equity (explicitly declined).
- One-account-per-strategy broker isolation (declined — large config/runner rework).
- Reconstructing historical unrealized P&L (not faithfully possible without historical marks).
