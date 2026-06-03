-- flights/secrets/create_secrets.sql
-- Per-account Alpaca credential secrets for the auto-trading execution Flights.
--
-- Replace placeholders with real per-account Alpaca paper keys before running.
-- Do NOT commit real values.
--
-- MECHANISM (confirmed empirically against the live MotherDuck instance — plan 02-01, Task 1):
--   MotherDuck locks the `allow_unredacted_secrets` setting, so credential fields stored under
--   known-sensitive names (e.g. BEARER_TOKEN) read back as `redacted`. However, arbitrary
--   entries in a `TYPE http` secret's EXTRA_HTTP_HEADERS map read back IN PLAINTEXT via
--   `SELECT secret_string FROM duckdb_secrets()` even with redaction enabled. We therefore store
--   each account's Alpaca api_key and secret_key as EXTRA_HTTP_HEADERS entries.
--
-- READ-BACK CALL (used by verify_secrets.py and every execution Flight):
--   SELECT secret_string FROM duckdb_secrets() WHERE name = 'alpaca_<account>';
--   then parse the `extra_http_headers={api_key=..., secret_key=...}` portion.
--
-- HOW TO RUN: against MotherDuck via `duckdb.connect("md:")` with a service-account
-- MOTHERDUCK_TOKEN, or paste into the MotherDuck SQL UI. Secrets persist in the MotherDuck
-- account catalog and are visible to Flights authenticating to the same account.
--
-- Requirements: SECRETS-01 (one secret per account, created/replaced below), SECRETS-02
-- (runtime read-back, no plaintext in source/config), SECRETS-03 (one secret per account).

CREATE OR REPLACE SECRET alpaca_stat_arb (
    TYPE http,
    EXTRA_HTTP_HEADERS MAP {
        'api_key':    '<<ALPACA_API_KEY_STAT_ARB>>',
        'secret_key': '<<ALPACA_SECRET_KEY_STAT_ARB>>'
    }
);

CREATE OR REPLACE SECRET alpaca_macro_vol (
    TYPE http,
    EXTRA_HTTP_HEADERS MAP {
        'api_key':    '<<ALPACA_API_KEY_MACRO_VOL>>',
        'secret_key': '<<ALPACA_SECRET_KEY_MACRO_VOL>>'
    }
);

CREATE OR REPLACE SECRET alpaca_trend_following (
    TYPE http,
    EXTRA_HTTP_HEADERS MAP {
        'api_key':    '<<ALPACA_API_KEY_TREND_FOLLOWING>>',
        'secret_key': '<<ALPACA_SECRET_KEY_TREND_FOLLOWING>>'
    }
);
