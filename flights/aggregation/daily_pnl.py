"""daily-pnl-aggregation Flight.

Aggregates the prior trading day's filled trades into per-strategy / per-account daily metrics
and writes them to trading.main.daily_pnl idempotently (re-running the same date overwrites,
never duplicates). Pure MotherDuck SQL — no Alpaca credentials, only the MOTHERDUCK_TOKEN
injected by the Flight runtime via access_token_name.

Schedule: 6 PM ET Mon-Fri so all fills are confirmed before aggregating (PITFALLS #7).
Correct UTC cron: "0 22 * * 1-5" in summer (EDT = UTC-4) / "0 23 * * 1-5" in winter (EST = UTC-5).
(The plan/REQUIREMENTS AGG-03 had these two DST values swapped; corrected here — 18:00 EDT is
22:00 UTC, matching the exec-flight cron convention.)

"Prior trading day" is CURRENT_DATE - INTERVAL 1 DAY (AGG-02). Per the plan's v1.0
simplification, a Monday run aggregates Sunday (zero rows, no trades) rather than the preceding
Friday — weekend dates simply produce no filled trades, so this is harmless.
"""
from collections import defaultdict

import duckdb

# Prior trading day in US Eastern (the market's calendar), not UTC — so a fill near the US close
# (e.g. 15:45 ET) lands on the correct trading day instead of being pushed to the next UTC date.
PRIOR_DAY = "((now() AT TIME ZONE 'America/New_York')::DATE - INTERVAL 1 DAY)::DATE"

DDL = """
CREATE TABLE IF NOT EXISTS trading.main.daily_pnl (
    date           DATE NOT NULL,
    strategy_name  VARCHAR NOT NULL,
    account_name   VARCHAR NOT NULL,
    realized_pnl   DECIMAL(18,4),
    trade_count    INTEGER,
    win_count      INTEGER,
    sharpe_7d      DECIMAL(18,6),
    max_drawdown   DECIMAL(18,6),
    PRIMARY KEY (date, strategy_name, account_name)
)
"""

# Step 1 — realized P&L. trades.pnl is never populated by the live fill path (update_fill always
# writes pnl=NULL), so SUM(pnl) would be NULL forever. Instead we recompute realized P&L from the
# fills themselves with average-cost accounting (signed position handles both long sells and short
# covers), attributing each closing trade's P&L to the Eastern trading day it filled. We read the
# full fill history (cost basis spans days) and write only the prior day's rows.
FILLS_SQL = """
SELECT strategy_name, account_name, symbol, side, qty, filled_avg_price,
       (filled_at AT TIME ZONE 'America/New_York')::DATE AS d
FROM trading.main.trades
WHERE status = 'filled' AND filled_at IS NOT NULL AND filled_avg_price IS NOT NULL
ORDER BY filled_at
"""

# ON CONFLICT DO UPDATE on the non-key metric columns only (AGG-05); never the PK columns
# (DuckDB bug #16698 / PITFALLS #4). sharpe_7d / max_drawdown are filled by step 2.
UPSERT_ROW = """
INSERT INTO trading.main.daily_pnl
    (date, strategy_name, account_name, realized_pnl, trade_count, win_count, sharpe_7d, max_drawdown)
VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
ON CONFLICT (date, strategy_name, account_name) DO UPDATE SET
    realized_pnl = EXCLUDED.realized_pnl,
    trade_count  = EXCLUDED.trade_count,
    win_count    = EXCLUDED.win_count
"""


def _realized_metrics(fills):
    """Average-cost realized P&L per (strategy, account, day) from chronologically-ordered fills.

    Each fill is (strategy, account, symbol, side, qty, price, day). A buy is +qty, a sell -qty;
    a signed running position lets the same logic realize P&L on long sells and short covers, and
    handle flips. Returns {(strategy, account, day): {realized, trades, wins}}.
    """
    book = defaultdict(lambda: [0.0, 0.0])   # (strategy, account, symbol) -> [signed_qty, avg_cost]
    out = defaultdict(lambda: {"realized": 0.0, "trades": 0, "wins": 0})
    for strategy, account, symbol, side, qty, price, day in fills:
        qty = float(qty)
        price = float(price)
        delta = qty if str(side).lower() == "buy" else -qty
        key = (strategy, account, symbol)
        pos, avg = book[key]
        agg = out[(strategy, account, day)]
        agg["trades"] += 1

        realized = 0.0
        if pos == 0 or (pos > 0) == (delta > 0):
            # opening or adding in the same direction -> blend the average cost
            new_pos = pos + delta
            if new_pos != 0:
                avg = (avg * abs(pos) + price * abs(delta)) / abs(new_pos)
            pos = new_pos
        else:
            # reducing / closing / flipping the position
            closing = min(abs(delta), abs(pos))
            realized = (price - avg) * closing if pos > 0 else (avg - price) * closing
            pos = pos + delta
            if abs(delta) > closing:   # flipped past flat -> new leg is priced at this fill
                avg = price
            elif pos == 0:
                avg = 0.0
            # partial close keeps the existing avg cost for the remaining shares

        book[key] = [pos, avg]
        if realized:
            agg["realized"] += realized
            if realized > 0:
                agg["wins"] += 1
    return out

# Step 2 — compute sharpe_7d (mean/stddev of the trailing 7 daily realized_pnl values per
# strategy/account; NULL when <7 days of history or zero variance) and max_drawdown (max
# peak-to-trough of cumulative daily realized_pnl over all history). Computed from daily_pnl's
# own history, never a hardcoded constant.
UPDATE_METRICS = f"""
UPDATE trading.main.daily_pnl AS d
SET sharpe_7d = m.sharpe_7d,
    max_drawdown = m.max_drawdown
FROM (
    WITH base AS (
        SELECT strategy_name, account_name, date, realized_pnl
        FROM trading.main.daily_pnl
        WHERE date <= {PRIOR_DAY}
    ),
    last7 AS (
        SELECT strategy_name, account_name, realized_pnl
        FROM (
            SELECT strategy_name, account_name, realized_pnl,
                   ROW_NUMBER() OVER (PARTITION BY strategy_name, account_name ORDER BY date DESC) AS rn
            FROM base
        )
        WHERE rn <= 7
    ),
    sharpe AS (
        SELECT strategy_name, account_name,
               CASE WHEN COUNT(*) >= 7 AND STDDEV_SAMP(realized_pnl) > 0
                    THEN AVG(realized_pnl) / STDDEV_SAMP(realized_pnl)
               END AS sharpe_7d
        FROM last7
        GROUP BY strategy_name, account_name
    ),
    cum AS (
        SELECT strategy_name, account_name, date,
               SUM(realized_pnl) OVER (PARTITION BY strategy_name, account_name ORDER BY date
                                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_pnl
        FROM base
    ),
    drawdown AS (
        SELECT strategy_name, account_name, MAX(peak - cum_pnl) AS max_drawdown
        FROM (
            SELECT strategy_name, account_name, cum_pnl,
                   MAX(cum_pnl) OVER (PARTITION BY strategy_name, account_name ORDER BY date
                                      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS peak
            FROM cum
        )
        GROUP BY strategy_name, account_name
    )
    SELECT sharpe.strategy_name, sharpe.account_name, sharpe.sharpe_7d, drawdown.max_drawdown
    FROM sharpe JOIN drawdown USING (strategy_name, account_name)
) AS m
WHERE d.date = {PRIOR_DAY}
  AND d.strategy_name = m.strategy_name
  AND d.account_name = m.account_name
"""


def main():
    con = duckdb.connect("md:")
    con.execute("CREATE DATABASE IF NOT EXISTS trading")
    con.execute(DDL)

    prior_day = con.execute(f"SELECT {PRIOR_DAY}").fetchone()[0]
    metrics = _realized_metrics(con.execute(FILLS_SQL).fetchall())
    written = 0
    for (strategy, account, day), m in metrics.items():
        if day != prior_day:
            continue
        con.execute(
            UPSERT_ROW,
            [prior_day, strategy, account, m["realized"], m["trades"], m["wins"]],
        )
        written += 1

    con.execute(UPDATE_METRICS)
    print(f"daily_pnl rows for prior day: {written}")


if __name__ == "__main__":
    main()
