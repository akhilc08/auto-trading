---
phase: 02-flights
plan: 01
subsystem: secrets
tags: [secrets, motherduck, alpaca, credentials]
requires: []
provides:
  - "alpaca_<account> MotherDuck secrets (TYPE http + EXTRA_HTTP_HEADERS) — plaintext read-back mechanism"
  - "flights/secrets/create_secrets.sql template"
  - "flights/secrets/verify_secrets.py read-back proof + parse_credentials() helper"
affects: [02-02-exec-flight-stat-arb, 02-03-exec-flights-macro-trend]
tech-stack:
  added: []
  patterns:
    - "Store Alpaca api_key/secret_key as EXTRA_HTTP_HEADERS map entries on a TYPE http secret; read back via SELECT secret_string FROM duckdb_secrets() and parse extra_http_headers={...}"
key-files:
  created:
    - flights/secrets/create_secrets.sql
    - flights/secrets/verify_secrets.py
    - flights/secrets/README.md
  modified: []
key-decisions:
  - "MotherDuck locks allow_unredacted_secrets, so BEARER_TOKEN / known-sensitive fields read back as 'redacted'. Arbitrary EXTRA_HTTP_HEADERS entries on a TYPE http secret DO read back in plaintext even with redaction on — confirmed empirically. This is the credential mechanism for all execution Flights."
  - "Created the trading database + 4 tables (trades, positions, portfolio_snapshots, daily_pnl) on the live MotherDuck instance — Phase 1 produced the DDL in core/motherduck_logger.py but never deployed it. DDL copied verbatim from Phase 1."
requirements-completed: [SECRETS-01, SECRETS-02, SECRETS-03]
duration: "~35 min"
completed: "2026-06-03"
---

# Phase 02 Plan 01: Secrets Summary

Per-account Alpaca credential mechanism for MotherDuck Flights: store `api_key`/`secret_key` as `EXTRA_HTTP_HEADERS` entries on a `TYPE http` secret, which read back in plaintext via `duckdb_secrets()` despite MotherDuck locking unredacted-secret display.

## What Was Built

- **Confirmed secret mechanism (Task 1 — blocking-human checkpoint, resolved empirically):** Probed the live MotherDuck instance. Only `http`, `iceberg`, `ducklake` secret types are registered; `allow_unredacted_secrets` is **locked** (cannot be enabled). Discovered that arbitrary `EXTRA_HTTP_HEADERS` map entries on a `TYPE http` secret read back in **plaintext** via `SELECT secret_string FROM duckdb_secrets()` even with redaction on (only known-sensitive fields like `BEARER_TOKEN` are redacted).
- **`flights/secrets/create_secrets.sql`** — three `CREATE OR REPLACE SECRET` statements (`alpaca_stat_arb`, `alpaca_macro_vol`, `alpaca_trend_following`), placeholders only.
- **`flights/secrets/verify_secrets.py`** — `main()` connects via `duckdb.connect("md:")`, reads each secret back, asserts both fields non-empty, prints `OK <name>` with field lengths only (never raw values). Includes `parse_credentials()` to extract the headers map.
- **`flights/secrets/README.md`** — operator runbook (which secret → which Flight, read-back call, service-account token requirement).
- **Infrastructure created on live MotherDuck:** `trading` database + 4 tables matching Phase 1's `core/motherduck_logger.py` DDL exactly (Phase 1 code was never deployed to the cloud).

## Confirmed read-back call (downstream plans 02-02/02-03 depend on this)

```sql
SELECT secret_string FROM duckdb_secrets() WHERE name = 'alpaca_<account>';
-- secret_string contains: ...;extra_http_headers={api_key=<KEY>, secret_key=<SECRET>}
```

Create form: `CREATE OR REPLACE SECRET alpaca_<account> (TYPE http, EXTRA_HTTP_HEADERS MAP{'api_key':'...','secret_key':'...'});`

## Deviations from Plan

**[Scope addition — user-requested]** The plan assumed Phase 1's `trading` database/schema already existed. It did not (Phase 1 produced code but never deployed). At the user's explicit request, created the `trading` database and all 4 tables on the live MotherDuck instance using Phase 1's exact DDL. This unblocks 02-04 (aggregation) and 02-02/03 (execution writes).

The plan's design notes assumed a "generic key-value secret type" might exist; empirically it does not — the `TYPE http` + `EXTRA_HTTP_HEADERS` path is the confirmed viable mechanism. No replanning of 02-02/03 needed (mechanism works).

**Total deviations:** 1 (scope addition, user-approved). **Impact:** positive — infrastructure now live.

## Tasks
- Task 1 (checkpoint:human-verify): mechanism confirmed empirically. ✓
- Task 2 (auto): create_secrets.sql + README.md. ✓ (automated verify PASS)
- Task 3 (auto): verify_secrets.py. ✓ (ast verify PASS; parse_credentials unit-tested in .venv)

## Operator Action — DONE
All three real secrets were created on the live MotherDuck instance and read-back was verified
via `duckdb_secrets()` (plaintext, redaction on): `alpaca_stat_arb` (api_key 26 / secret_key 44),
`alpaca_macro_vol` (26/43), `alpaca_trend_following` (26/42). The third account is labeled
`stock_alpha` in Alpaca / `core/accounts.py` but maps to the `alpaca_trend_following` secret used
by the `exec-trend-following` Flight (EXEC-03) — same physical account.

Remaining (operator, when convenient): run `MOTHERDUCK_TOKEN=<service-account-token> python
flights/secrets/verify_secrets.py` from a shell to confirm read-back through the exact Flight code
path (MCP read-back already proved the mechanism).

## Self-Check: PASSED
- key-files.created exist on disk: ✓ (create_secrets.sql, verify_secrets.py, README.md)
- Commits present: ✓ (bbeec4b, c054ee7)
- Task 2 acceptance criteria: PASS (3 CREATE OR REPLACE SECRET, all 3 names, no key pattern)
- Task 3 acceptance criteria: PASS (main(), duckdb.connect("md:"), 3 names; parser unit test PASS)

## Next
Ready for 02-04 (aggregation) and 02-02 (exec-stat-arb). Note: execution Flights can be written now; their live verification needs the real secrets above.
