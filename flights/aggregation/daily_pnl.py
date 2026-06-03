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
import duckdb

PRIOR_DAY = "(CURRENT_DATE - INTERVAL 1 DAY)::DATE"

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

# Step 1 — upsert the prior day's base metrics. ON CONFLICT DO UPDATE on the non-key metric
# columns only (AGG-05); never the PK columns (DuckDB bug #16698 / PITFALLS #4). sharpe_7d and
# max_drawdown are filled by step 2 (they depend on history including this row).
UPSERT = f"""
INSERT INTO trading.main.daily_pnl
    (date, strategy_name, account_name, realized_pnl, trade_count, win_count, sharpe_7d, max_drawdown)
SELECT
    {PRIOR_DAY} AS date,
    strategy_name,
    account_name,
    SUM(pnl)                                  AS realized_pnl,
    COUNT(*)                                  AS trade_count,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)  AS win_count,
    NULL                                      AS sharpe_7d,
    NULL                                      AS max_drawdown
FROM trading.main.trades
WHERE status = 'filled'
  AND filled_at::DATE = {PRIOR_DAY}
GROUP BY strategy_name, account_name
ON CONFLICT (date, strategy_name, account_name) DO UPDATE SET
    realized_pnl = EXCLUDED.realized_pnl,
    trade_count  = EXCLUDED.trade_count,
    win_count    = EXCLUDED.win_count,
    sharpe_7d    = EXCLUDED.sharpe_7d,
    max_drawdown = EXCLUDED.max_drawdown
"""

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
    con.execute(UPSERT)
    con.execute(UPDATE_METRICS)
    rows = con.execute(
        f"SELECT COUNT(*) FROM trading.main.daily_pnl WHERE date = {PRIOR_DAY}"
    ).fetchone()[0]
    print(f"daily_pnl rows for prior day: {rows}")


if __name__ == "__main__":
    main()
