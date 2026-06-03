# Technology Stack

**Project:** auto-trading — MotherDuck Cloud Deployment milestone
**Researched:** 2026-06-03 (rewritten via MotherDuck MCP tools — authoritative)
**Confidence:** HIGH

## New Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `duckdb` | `==1.5.2` | Python-to-MotherDuck write layer; pin exactly for Flight reproducibility |

No other new Python dependencies. The MotherDuck extension is bundled in the standard `duckdb` pip package.

## MotherDuck Flights (Real, Shipping Product)

A Flight is a **Python program that runs on MotherDuck compute**:
- Single Python entrypoint with `def main():`
- `requirements_txt`: pip packages (pin versions for reproducibility — unpin = PyPI latest which may break)
- `access_token_name`: name of a MotherDuck access token; provided at runtime as `MOTHERDUCK_TOKEN` env var
- `config`: non-secret key-value pairs exposed as env vars. **NOT for API keys — unencrypted**
- `schedule_cron`: 5-field cron in UTC (e.g. `"0 23 * * 1-5"` = 6 PM ET Mon–Fri in summer)
- Runtime: 2 CPU cores, 16GB RAM, ~150GB scratch at `/tmp/`
- Connect: `duckdb.connect("md:")` inside the flight (token auto-injected via env var)

**Flights are the right tool for the aggregation pipeline.** Runs on MotherDuck compute, pip packages available, cron-scheduled, no additional infra.

**Flights are NOT right for strategy execution.** Alpaca API keys cannot go in Flight `config` (unencrypted). Strategy execution stays in GitHub Actions (encrypted secrets).

## MotherDuck Dives (Real, Shipping Product)

A Dive is a **React function component** with a default export:
- `useSQLQuery` from `@motherduck/react-sql-query` for data fetching — `data` is the rows array directly (no `.rows`)
- Charts via `recharts` (LineChart, BarChart, AreaChart, etc.)
- Tailwind CSS utilities — no arbitrary bracket syntax (`bg-[#hex]` does NOT work; use `style={{}}`)
- Created via `save_dive` MCP tool or `MD_CREATE_DIVE` SQL function
- Queries live MotherDuck data on each load
- Always use `N()` helper to convert BigInt/Decimal: `const N = (v) => v != null ? Number(v) : 0`
- Table names must be fully qualified and double-quoted: `"database"."schema"."table"`

## GitHub Actions (Strategy Execution Only)

- Required because Alpaca API keys need encrypted secrets (not available in Flights `config`)
- `actions/checkout@v4`, `actions/setup-python@v5`
- `timezone:` field on cron schedules supported (March 2026) — use `"America/New_York"`
- `workflow_dispatch` for manual testing
- **Risk:** Scheduled workflows disabled after 60 days of repo inactivity

## Authentication

- MotherDuck (Python → MotherDuck writes): `duckdb.connect("md:", config={"motherduck_token": os.environ["MOTHERDUCK_TOKEN"]})` — or export `MOTHERDUCK_TOKEN` as env var and `duckdb.connect("md:")` picks it up
- MotherDuck (Flights): set `access_token_name` to a service account token label (not personal token)
- Alpaca: per-account API keys in GitHub Actions secrets only
