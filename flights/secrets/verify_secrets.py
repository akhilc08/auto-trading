"""Runtime proof that execution Flights can read Alpaca credentials back from MotherDuck.

Mirrors how a Flight runs: connects via duckdb.connect("md:") (MOTHERDUCK_TOKEN injected by
the runtime / environment) and reads each per-account secret back. Credentials are stored as
EXTRA_HTTP_HEADERS entries on a TYPE http secret, which read back in plaintext from
duckdb_secrets().secret_string even though MotherDuck locks unredacted-secret display.

Prints `OK <name>` (with field lengths only) for each readable secret, `MISSING <name>` and
exits non-zero otherwise. NEVER prints raw credential values. Reads NO plaintext credential
from any file — only from the live MotherDuck secret store.

Usage:
    MOTHERDUCK_TOKEN=<service-account-token> python flights/secrets/verify_secrets.py
"""
import re
import sys

import duckdb

SECRET_NAMES = ["alpaca_stat_arb", "alpaca_macro_vol", "alpaca_trend_following"]


def parse_credentials(secret_string: str) -> dict:
    """Extract the EXTRA_HTTP_HEADERS map from a duckdb_secrets() secret_string.

    Format: '...;extra_http_headers={api_key=VALUE1, secret_key=VALUE2}'. Values are split on
    the first '=' so credential values containing '=' are preserved. Alpaca keys contain no
    ', ' so the comma split is safe.
    """
    match = re.search(r"extra_http_headers=\{(.*)\}", secret_string)
    if not match:
        return {}
    headers = {}
    for token in match.group(1).split(", "):
        if "=" in token:
            key, value = token.split("=", 1)
            headers[key.strip()] = value
    return headers


def main() -> None:
    con = duckdb.connect("md:")  # MOTHERDUCK_TOKEN auto-injected from env (matches Flight runtime)
    missing = False
    for name in SECRET_NAMES:
        rows = con.execute(
            "SELECT secret_string FROM duckdb_secrets() WHERE name = ?", [name]
        ).fetchall()
        if not rows:
            print(f"MISSING {name}")
            missing = True
            continue
        creds = parse_credentials(rows[0][0])
        api_key = creds.get("api_key", "")
        secret_key = creds.get("secret_key", "")
        if not api_key or not secret_key:
            print(f"MISSING {name} (api_key or secret_key empty)")
            missing = True
            continue
        print(f"OK {name} (api_key len={len(api_key)}, secret_key len={len(secret_key)})")
    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
