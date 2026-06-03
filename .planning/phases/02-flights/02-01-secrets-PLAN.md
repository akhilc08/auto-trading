---
phase: 02-flights
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - flights/secrets/create_secrets.sql
  - flights/secrets/verify_secrets.py
  - flights/secrets/README.md
autonomous: false
requirements: [SECRETS-01, SECRETS-02, SECRETS-03]
must_haves:
  truths:
    - "Each account's Alpaca API key and secret exist as a named MotherDuck secret, created via CREATE OR REPLACE SECRET"
    - "A Flight (or duckdb.connect('md:')) can read an Alpaca key/secret back from the named secret at runtime — no plaintext credential in any SQL/Python source or Flight config"
    - "Each account has its own secret (alpaca_stat_arb, alpaca_macro_vol, alpaca_trend_following) so a Flight reads only the credentials for its account"
  artifacts:
    - path: "flights/secrets/create_secrets.sql"
      provides: "CREATE OR REPLACE SECRET template (placeholders for keys, not real values)"
      contains: "CREATE OR REPLACE SECRET"
    - path: "flights/secrets/verify_secrets.py"
      provides: "Runtime read-back proof that a Flight can retrieve Alpaca creds from a secret"
      min_lines: 20
    - path: "flights/secrets/README.md"
      provides: "Operator runbook for creating the three per-account secrets"
  key_links:
    - from: "flights/secrets/verify_secrets.py"
      to: "duckdb.connect('md:')"
      via: "secret read-back query"
      pattern: "duckdb\\.connect"
---

<objective>
Establish the credential mechanism for all execution Flights: store each Alpaca account's
API key and secret as a named, per-account MotherDuck (DuckDB) secret using
`CREATE OR REPLACE SECRET`, and prove at runtime that a Flight process connecting via
`duckdb.connect("md:")` can read those credentials back without any plaintext credential
appearing in Flight `source_code` or `config`.

This is the foundation every execution Flight (plans 02, 03) depends on. It replaces the
research-era assumption that Alpaca keys must live in GitHub Actions secrets: per the v1.0
requirements (SECRETS-01/02/03), keys live as encrypted DuckDB secrets in MotherDuck instead,
which is why execution can move onto Flights at all.

Purpose: Without a working, verified read-back of Alpaca creds from a DuckDB secret, the three
execution Flights cannot authenticate to Alpaca, and the security posture (no plaintext keys)
cannot be met.
Output: A reusable SQL secret-creation template, a runtime verification script, an operator
runbook, and three live per-account secrets in MotherDuck.
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
@.planning/research/STACK.md
@.planning/research/PITFALLS.md
@core/accounts.py
@core/alpaca_client.py
</context>

<design_notes>
Decisions made for this phase (no CONTEXT.md / RESEARCH.md provided for the phase; these were
derived from REQUIREMENTS.md + milestone research and must be honored by all Phase 2 plans):

- **Secret naming:** one secret per account, named `alpaca_<account>`:
  `alpaca_stat_arb`, `alpaca_macro_vol`, `alpaca_trend_following`. (SECRETS-03 — per-account scope.)
- **Account names** follow the EXEC requirement text exactly: `stat_arb`, `macro_vol`,
  `trend_following`. NOTE: `core/accounts.py` currently uses `stat_arb`, `macro_vol`,
  `stock_alpha` with a different strategy split. The Flights phase follows the EXEC-01/02/03
  groupings (authoritative for this phase), and each Flight bundles its own strategy list —
  it does NOT import `core/accounts.py`. Do NOT modify `core/accounts.py`.
- **Secret mechanism:** DuckDB supports a generic key-value secret type that stores arbitrary
  named fields and is readable back via the `duckdb_secrets()` table function / secret-access
  path. The documented cloud-storage secret types (S3/GCS/R2/AZURE/HUGGINGFACE) are NOT the
  right fit — those redact the secret string. Task 1 MUST empirically confirm, against the
  live MotherDuck instance, the exact secret TYPE and read-back call that returns the stored
  key/secret values in plaintext to the Flight process. If the generic read-back path does not
  exist on this MotherDuck instance, STOP and surface the gap (see acceptance criteria) — do
  not silently fall back to plaintext-in-config.
- **No real keys in the repo:** `create_secrets.sql` contains placeholders only
  (`<<ALPACA_API_KEY_STAT_ARB>>` etc.). Real values are pasted by the operator at runtime.
</design_notes>

<artifacts_this_phase_produces>
This plan creates:
- **Secrets (live, in MotherDuck):** `alpaca_stat_arb`, `alpaca_macro_vol`, `alpaca_trend_following`
- **SQL object:** `flights/secrets/create_secrets.sql` — `CREATE OR REPLACE SECRET` template
- **File:** `flights/secrets/verify_secrets.py` — runtime read-back proof
- **File:** `flights/secrets/README.md` — operator runbook
- **Convention:** secret naming `alpaca_<account>`, secret fields `api_key` / `secret_key`
</artifacts_this_phase_produces>

<tasks>

<task type="checkpoint:human-verify" gate="blocking-human">
  <name>Task 1: Confirm DuckDB generic-secret read-back mechanism on the live MotherDuck instance</name>
  <read_first>
    - .planning/research/STACK.md (Flights connect via duckdb.connect("md:"); secret/config notes)
    - .planning/research/PITFALLS.md (#2 Flight config not encrypted — why we use secrets instead)
    - .planning/REQUIREMENTS.md (SECRETS-01/02/03)
  </read_first>
  <what-built>
    Nothing built yet — this is a verification gate that resolves the one load-bearing
    unknown before any Flight is created: whether a Flight can read an Alpaca API key/secret
    BACK from a DuckDB secret in plaintext at runtime. DuckDB's documented secret types
    (S3/GCS/R2/AZURE/HUGGINGFACE) redact secret values. We need a generic/custom secret type
    whose stored fields can be retrieved by the Flight process.
  </what-built>
  <how-to-verify>
    Run against the live MotherDuck instance (use the MotherDuck MCP query tool, or
    `duckdb.connect("md:")` with MOTHERDUCK_TOKEN):
    1. Create a throwaway test secret with a generic key-value type, e.g.
       `CREATE OR REPLACE SECRET _gsd_secret_probe (TYPE <type>, api_key 'PROBE_KEY', secret_key 'PROBE_SECRET');`
       (try the generic type first; if rejected, capture the exact error).
    2. Read it back: `SELECT name, type, secret_string FROM duckdb_secrets() WHERE name = '_gsd_secret_probe';`
       — and any other read-back call (e.g. a secret-access function) needed to return the
       plaintext `api_key` / `secret_key`.
    3. Confirm the values `PROBE_KEY` / `PROBE_SECRET` are returned in plaintext to the caller
       (NOT redacted as `redacted` or `***`).
    4. Drop the probe: `DROP SECRET _gsd_secret_probe;`
    Record in the resume note: the exact working `CREATE ... SECRET` TYPE and the exact
    read-back call. If NO read-back path returns plaintext values, record that — plans 02/03
    will need to be replanned (the SECRETS approach may not be viable on this instance).
  </how-to-verify>
  <acceptance_criteria>
    - Operator confirms the exact `CREATE OR REPLACE SECRET` syntax (TYPE + field names) that
      stores `api_key` and `secret_key` and is accepted by the live instance.
    - Operator confirms the exact read-back call that returns `PROBE_KEY`/`PROBE_SECRET` in
      plaintext, OR explicitly reports that no plaintext read-back exists (blocking finding).
    - The throwaway `_gsd_secret_probe` secret is dropped after verification.
  </acceptance_criteria>
  <resume-signal>
    Reply with the confirmed `CREATE ... SECRET` TYPE + field names and the read-back call
    (e.g. "TYPE custom works; read via duckdb_secrets().secret_string"), OR "no plaintext
    read-back — replan needed".
  </resume-signal>
</task>

<task type="auto">
  <name>Task 2: Write the secret-creation SQL template and operator runbook</name>
  <files>flights/secrets/create_secrets.sql, flights/secrets/README.md</files>
  <read_first>
    - flights/secrets/ (does not exist yet — create the directory)
    - .planning/REQUIREMENTS.md (SECRETS-01: CREATE OR REPLACE SECRET for stat_arb, macro_vol, trend_following; SECRETS-03: per-account scope)
    - core/accounts.py (account names reference; do NOT import or modify)
    - The Task 1 resume note (confirmed secret TYPE + field names)
  </read_first>
  <action>
    Create `flights/secrets/create_secrets.sql` containing three `CREATE OR REPLACE SECRET`
    statements — one per account — named `alpaca_stat_arb`, `alpaca_macro_vol`,
    `alpaca_trend_following`, using the secret TYPE and field names confirmed in Task 1, with
    fields `api_key` and `secret_key`. Values MUST be literal placeholders
    `<<ALPACA_API_KEY_STAT_ARB>>`, `<<ALPACA_SECRET_KEY_STAT_ARB>>`, and the macro_vol /
    trend_following equivalents — NEVER real credentials. Add a top-of-file SQL comment stating
    "Replace placeholders with real per-account Alpaca paper keys before running. Do NOT commit
    real values." Create `flights/secrets/README.md` documenting: which account each secret
    serves, which Flight reads it (exec-stat-arb / exec-macro-vol / exec-trend-following), the
    exact read-back call from Task 1, and the rule that placeholders are filled in at runtime
    only. Reference SECRETS-01, SECRETS-02, SECRETS-03 in the README.
  </action>
  <verify>
    <automated>test -f flights/secrets/create_secrets.sql && grep -c 'CREATE OR REPLACE SECRET' flights/secrets/create_secrets.sql | grep -qx 3 && grep -q 'alpaca_stat_arb' flights/secrets/create_secrets.sql && grep -q 'alpaca_macro_vol' flights/secrets/create_secrets.sql && grep -q 'alpaca_trend_following' flights/secrets/create_secrets.sql && ! grep -Eiq 'PK[A-Z0-9]{16,}|sk-[A-Za-z0-9]{20,}' flights/secrets/create_secrets.sql && echo PASS</automated>
  </verify>
  <acceptance_criteria>
    - `flights/secrets/create_secrets.sql` contains exactly 3 `CREATE OR REPLACE SECRET` statements.
    - Secret names present: `alpaca_stat_arb`, `alpaca_macro_vol`, `alpaca_trend_following`.
    - Every credential value is a `<<...>>` placeholder; the file contains NO real key pattern
      (no `PK...`, no Alpaca-shaped secret strings). The grep guard above passes.
    - `README.md` documents the read-back call and maps each secret to its consuming Flight and
      cites SECRETS-01/02/03.
  </acceptance_criteria>
  <done>create_secrets.sql has 3 placeholder-only CREATE OR REPLACE SECRET statements; README documents read-back and Flight mapping.</done>
</task>

<task type="auto">
  <name>Task 3: Write the runtime secret read-back verification script</name>
  <files>flights/secrets/verify_secrets.py</files>
  <read_first>
    - flights/secrets/create_secrets.sql (secret names + field names from Task 2)
    - .planning/research/STACK.md (duckdb.connect("md:") picks up MOTHERDUCK_TOKEN)
    - The Task 1 resume note (read-back call)
  </read_first>
  <action>
    Create `flights/secrets/verify_secrets.py` with a `def main():` that mirrors how a Flight
    runs: connect with `duckdb.connect("md:")` (token auto-injected via MOTHERDUCK_TOKEN env
    var, matching Flight runtime; do NOT hardcode a token), then for each of the three secret
    names (`alpaca_stat_arb`, `alpaca_macro_vol`, `alpaca_trend_following`) execute the
    read-back call confirmed in Task 1 to retrieve `api_key` and `secret_key`. Assert each
    secret exists and both fields are non-empty, and print `OK <secret_name>` for each — but
    NEVER print the actual key/secret values (print only the secret name and field lengths).
    On a missing secret, print `MISSING <secret_name>` and exit non-zero. The script reads NO
    plaintext credential from any file — only from the live secret store.
  </action>
  <verify>
    <automated>python -c "import ast,sys; t=ast.parse(open('flights/secrets/verify_secrets.py').read()); fns=[n.name for n in ast.walk(t) if isinstance(n,ast.FunctionDef)]; assert 'main' in fns, 'no main()'; src=open('flights/secrets/verify_secrets.py').read(); assert 'duckdb.connect(\"md:\")' in src or \"duckdb.connect('md:')\" in src, 'no md connect'; assert 'alpaca_stat_arb' in src and 'alpaca_macro_vol' in src and 'alpaca_trend_following' in src; print('PASS')"</automated>
    <human-check>Run `MOTHERDUCK_TOKEN=<service-account-token> python flights/secrets/verify_secrets.py` after the operator has created the three real secrets — confirm it prints `OK` for all three and exits 0.</human-check>
  </verify>
  <acceptance_criteria>
    - `verify_secrets.py` defines `main()` and connects via `duckdb.connect("md:")`.
    - It checks all three secret names and asserts `api_key` + `secret_key` are non-empty.
    - It never prints raw credential values (only names and field lengths).
    - Running it against a populated secret store prints `OK` for all three and exits 0;
      against a missing secret it prints `MISSING <name>` and exits non-zero.
  </acceptance_criteria>
  <done>verify_secrets.py proves all three secrets are readable at runtime via duckdb.connect("md:") without leaking values.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator → MotherDuck | Real Alpaca credentials cross here once, when the operator runs create_secrets.sql with real values |
| MotherDuck secret store → Flight process | Flight reads credentials back at runtime via duckdb.connect("md:") |
| repo (git) → public | Source files must never contain real credentials |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-01 | Information Disclosure | create_secrets.sql committed with real keys | mitigate | File contains only `<<...>>` placeholders; Task 2 grep guard fails the build if any Alpaca-shaped key pattern (`PK...`, `sk-...`) appears |
| T-02-02 | Information Disclosure | verify_secrets.py logs credential values | mitigate | Script prints only secret name + field length, never the raw api_key/secret_key |
| T-02-03 | Information Disclosure | Secret values readable cross-account | mitigate | One secret per account (`alpaca_<account>`); SECRETS-03 per-account scope so each Flight reads only its own |
| T-02-04 | Tampering | DuckDB secret type that redacts values (wrong type chosen) | mitigate | Task 1 blocking-human checkpoint empirically confirms a read-back path returns plaintext before any Flight is built on it |
| T-02-05 | Spoofing | Personal MotherDuck token used instead of service account | mitigate | README mandates service-account token (PITFALLS #1); verify_secrets.py reads token from env, never hardcoded |
| T-02-SC | Tampering | duckdb pip install in downstream Flights | mitigate | duckdb pinned `==1.5.2` in plans 02/03/04; legitimacy covered there (duckdb is a first-party, well-known package) |
</threat_model>

<verification>
- All three secret names appear in create_secrets.sql with placeholder-only values.
- No real credential pattern appears in any committed file (grep guard).
- verify_secrets.py connects via duckdb.connect("md:") and proves read-back of all three secrets.
- Task 1 checkpoint confirmed the live read-back mechanism before any downstream Flight depends on it.
</verification>

<success_criteria>
- Alpaca credentials for stat_arb, macro_vol, trend_following exist as named DuckDB secrets in MotherDuck (SECRETS-01).
- A Flight-style `duckdb.connect("md:")` process reads those credentials back at runtime with no plaintext in source or config (SECRETS-02).
- Secrets are per-account so each Flight reads only its account's credentials (SECRETS-03).
</success_criteria>

<output>
Create `.planning/phases/02-flights/02-01-SUMMARY.md` when done. Record the confirmed secret
TYPE and read-back call (downstream plans 02/03 depend on it).
</output>
