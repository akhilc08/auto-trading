# `motherduck secrets` — Implementation Plan

## Goal

Add a first-class `secrets` command group to the MotherDuck CLI with `create`, `list`,
and `delete` subcommands, plus a parallel `flight secrets` group for flight secrets.
Creation defaults to **PERSISTENT**. When used by an agent, the agent hands the user a
command with a placeholder for the secret value that the user runs in their own terminal,
so the agent never sees the secret value.

## What a secret actually is (data model)

A secret is **not** a single env variable. It's a **named, typed bundle of fields**:

```
secret = (name: string, type: string, params: map<string, string>)
```

- **name** — the handle you reference it by (`my_s3`, `openai`). Not a credential.
- **type** — what the secret is *for*, from a fixed set (`s3`, `gcs`, `r2`, `azure`,
  `huggingface`, `http`, and the flights-only `flights`).
- **params** — a map of one or more `key=value` fields, the actual contents.

So one `create` command makes **one** secret. The multiple `key=value` pairs are the
*fields inside that one secret*, not separate secrets — there's only ever one name per
command, so there's no name collision. A simple API key is just name + type + one field;
an S3 credential is name + type + several fields (key id, secret, region) that are
meaningless apart, so they live together under one name.

```
secret "my_s3"   type=s3
├── key_id = AKIA...
├── secret = abc
└── region = us-east-1
```

## Why

There's no way to manage secrets from the CLI today — the only path is raw DuckDB SQL.
That's a pain, especially for agents, in three ways:

1. **The PERSISTENT footgun.** A bare `CREATE SECRET` is session-scoped and vanishes when
   the connection closes. Every CLI call is a fresh connection, so the secret is gone by
   the next command. You (or the agent) must remember `PERSISTENT`, and nothing warns you.
   In practice this confused the agent — it created a secret and then couldn't find where
   it went.

2. **Agents shouldn't handle raw secret values.** Setting a secret via raw SQL means the
   agent writes the value into the command, so it lands in the agent's transcript. Agents
   shouldn't be able to see raw secrets, and there's no safeguard today since the agent
   defaults to raw SQL.

3. **The raw-SQL escape hatch.** An agent could still run a raw `CREATE SECRET` with a
   value. Fix this by detecting a `CREATE SECRET` statement in the query tool and
   redirecting to the same "run this manually" message.

## DuckDB Secrets Commands

### `secrets create <name> --type <provider> <key>=<value> [<key>=<value> ...]`

Runs:

```sql
CREATE SECRET <name> IN MOTHERDUCK (TYPE <provider>, <key> <value>, ...)
```

- `<name>` is the secret's name; `--type` is the provider; each `<key>=<value>` becomes one
  field in the secret. Multiple pairs go into the **same** secret.
- Stored `IN MOTHERDUCK` — important, because a secret in MotherDuck can also be read by
  flights.
- Values are passed inline as arguments, and `create` defaults to **PERSISTENT** so the
  secret survives the next (fresh-connection) CLI call.
- Or load the fields from a file with `--env-file <path>` instead of inline pairs — one
  file = one secret (see [Providing the secret value](#providing-the-secret-value)).

### `secrets list`

Lists all secrets, **metadata only**: `name`, `type`, `provider`, `persistent`, `storage`,
`scope`. Never prints field values — `duckdb_secrets()` redaction is only partial, so list
explicitly projects the safe columns and excludes the value column.

### `secrets delete <name>`

Drops the secret. Defaults to **PERSISTENT** to match `create`.

## Flight Secrets Commands

A flight secret is the same bundle model, but always `TYPE FLIGHTS` and MotherDuck-only.
The type is fixed, so there's no `--type` flag — that's why it's a separate group.

### `flight secrets create <name> <key>=<value> [<key>=<value> ...]`

Runs:

```sql
CREATE SECRET <name> IN MOTHERDUCK (TYPE FLIGHTS, PARAMS MAP {'<key>': '<value>', ...})
```

- No `--type` — always `FLIGHTS`. Each `<key>=<value>` becomes one entry in the `PARAMS MAP`
  (multiple pairs, one secret), same as DuckDB secrets.
- `IN MOTHERDUCK` is mandatory, not just a default — a `FLIGHTS` secret can only exist there.
- Also accepts `--env-file <path>` (one file = one secret) — the natural fit here, since a
  `FLIGHTS` secret *is* a key-value map. See [Providing the secret value](#providing-the-secret-value).
- Everything else (inline values, PERSISTENT default, agent-safety) matches DuckDB secrets.

### `flight secrets list`

Lists all flight secrets, **metadata only**, similar to DuckDB secrets. Flight secrets are
even more opaque: the field keys *and* values are hidden, so list shows only the outer
metadata (`name`, `type`, `persistent`, `storage`, `scope`).

### `flight secrets delete <name>`

Runs the drop-secret command. MotherDuck-only, so no storage ambiguity.

## Providing the secret value

The value can come from a few places, and **where it comes from decides whether the value
touches the command** — which in turn decides whether the agent can run it:

| Source | Value in the command? | Who runs it | When |
|---|---|---|---|
| inline `key="value"` | **yes** | human only (placeholder flow below) | quick one-off |
| `--env-file <path>` | **no** (just a path) | agent or human | low-friction default; multi-field secrets |
| stdin (`< file` / pipe) | **no** | agent or human | scripting |

### `--env-file` — one file, one secret (kubectl-style)

A secret holds multiple `key=value` fields and a `.env` file is a flat list of `key=value`
lines, so the mapping is **one file per secret**: the name comes from the command, and
every line in the file becomes one field inside that secret.

```bash
motherduck flight secrets create alpaca --env-file ./alpaca.env
```

```bash
# alpaca.env
api_key=PK...
secret_key=9Bw...
```

→ one secret `alpaca` with both fields. **Multiple secrets = multiple files / commands** —
you don't pack two secrets into one file, since the flat format can't say which line
belongs to which secret.

This mirrors `kubectl create secret generic <name> --from-env-file`, where the file is the
*contents of one named secret*. (Note: `gh secret set --env-file` and `fly secrets import`
treat each `.env` line as its *own* single-value secret — that flat model can't represent a
multi-field secret, so it's the wrong precedent here.)

Because `--env-file` and stdin keep the value **out of the command**, the agent can build
*and run* them directly — no placeholder flow needed, and the value still never enters the
transcript (it lives in the user's `.env`). Caveat: a `.env` is plaintext on disk.

## Agent-Safety model

When the value is **inline**, `secrets create` is for the **human** to run in their
terminal, not the agent, because the command contains the real secret value. When secret
creation is needed and the human asks the agent to do it, the agent prints the exact
command with an `input_your_secret` placeholder and stops. The user fills in the real value
and runs it. The value never enters the agent's context.

When the value comes from `--env-file` or stdin (above), it isn't in the command at all, so
the agent can run it directly — this is the lower-friction, preferred path.

### How

When the agent tries to call `secrets create`, intercept it before execution and redirect:

```
"error": "restricted",
"message": f"`{tool_name}` cannot be called by an agent. "
           f"Tell the user to run: "
           f"`motherduck secrets create <name> --type http secret=\"input_your_secret\"` manually."
```

Apply the same interception to raw `CREATE SECRET` statements in the query tool (point 3
above), so the escape hatch routes to the same message.

### Example

Human:

> Create an openai secret on MotherDuck. Here's my key: `<actual key>`

Agent:

> I can't handle secrets directly. Run this in your terminal:
>
> ```
> motherduck secrets create openai --type http secret="input_your_secret"
> ```

The human runs that with the real value.

## Files

- Create `src/commands/resources/secrets.ts` — the `secrets` command group.
- Create the `flight secrets` subgroup under the existing `flight` command.
- Edit `src/commands/resources/index.ts` — register the secrets group.
- Edit `src/resources/sql.ts` — `buildCreateSecretSql` / `buildListSecretsSql` (safe
  columns only) / `buildDeleteSecretSql`, plus the `FLIGHTS` / `PARAMS MAP` variants.
- Add a small dotenv parser (`key=value` lines → fields) shared by both `create` commands
  for `--env-file`.
- Add builder unit tests alongside `sql.test.ts`.
- Add a `secrets` row to the README resource table.

## Deferred

- `update` / rotate — `--or-replace` on create covers it.
- Reading a value back — intentionally unsupported (list excludes the value column rather
  than trusting partial redaction).
