# Alpaca Credential Secrets (MotherDuck)

Operator runbook for storing each trading account's Alpaca API credentials as named MotherDuck
secrets, so the execution Flights can read them at runtime with **no plaintext credential in any
source file or Flight `config`**.

Requirements: **SECRETS-01** (one `CREATE OR REPLACE SECRET` per account), **SECRETS-02**
(Flights read credentials back at runtime; nothing in source/config), **SECRETS-03** (secrets
scoped per account so each Flight reads only its own).

## Mechanism (why `TYPE http` + `EXTRA_HTTP_HEADERS`)

MotherDuck **locks** the `allow_unredacted_secrets` setting, so any credential stored under a
known-sensitive field name (e.g. `BEARER_TOKEN`, `SECRET`) reads back as `redacted` and is
useless to the Flight. Verified empirically (plan 02-01, Task 1): **arbitrary entries in a
`TYPE http` secret's `EXTRA_HTTP_HEADERS` map read back in plaintext** via
`duckdb_secrets().secret_string`, even with redaction on. So each account's `api_key` and
`secret_key` are stored as `EXTRA_HTTP_HEADERS` entries.

**Read-back call** (used by `verify_secrets.py` and every execution Flight):

```sql
SELECT secret_string FROM duckdb_secrets() WHERE name = 'alpaca_<account>';
-- secret_string contains: ...;extra_http_headers={api_key=<KEY>, secret_key=<SECRET>}
```

Parse the `extra_http_headers={api_key=..., secret_key=...}` portion (see
`parse_credentials()` in `verify_secrets.py`).

## Secrets to create

| Secret name | Account | Consuming Flight |
|-------------|---------|------------------|
| `alpaca_stat_arb` | `stat_arb` | `exec-stat-arb` |
| `alpaca_macro_vol` | `macro_vol` | `exec-macro-vol` |
| `alpaca_trend_following` | `trend_following` | `exec-trend-following` |

Each secret holds two fields: `api_key` and `secret_key` (the Alpaca **paper** API key id and
secret for that account).

## How to create them

1. Get three pairs of Alpaca **paper-trading** API keys — one per account — from the Alpaca
   dashboard (https://app.alpaca.markets/ → Paper account → API Keys → Generate). Use a
   separate Alpaca account/key pair per strategy account so credentials stay isolated.
2. Open `create_secrets.sql` and replace every `<<...>>` placeholder with the real values.
   **Do not commit the edited file** — fill placeholders only at runtime.
3. Run it against MotherDuck, either:
   - **MotherDuck SQL UI**: paste the three `CREATE OR REPLACE SECRET` statements, or
   - **CLI**: `MOTHERDUCK_TOKEN=<service-account-token> python -c "import duckdb,sys; duckdb.connect('md:').execute(open('flights/secrets/create_secrets.sql').read())"`
4. Use a **service-account token** (MotherDuck Settings → Service Accounts), not a personal
   token (see PITFALLS #1). The same token label is set as `access_token_name` on each Flight.
5. Verify read-back:
   ```bash
   MOTHERDUCK_TOKEN=<service-account-token> python flights/secrets/verify_secrets.py
   ```
   Expect `OK alpaca_stat_arb ...`, `OK alpaca_macro_vol ...`, `OK alpaca_trend_following ...`
   and exit code 0. A `MISSING <name>` line + non-zero exit means that secret was not created.

## Notes

- Secrets created with `CREATE OR REPLACE SECRET` against `md:` persist in the MotherDuck
  account catalog and are visible to any Flight authenticating to the same account.
- `verify_secrets.py` prints only secret names and field **lengths**, never the raw key/secret.
- `create_secrets.sql` contains only `<<...>>` placeholders; a CI grep guard fails the build if
  any Alpaca-shaped key pattern appears in it.
