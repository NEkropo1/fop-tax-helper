# Architecture

A small Python backend (FastAPI, local only) plus a React/TypeScript wizard. The backend does all the
tax logic; the UI only shows state and sends the user's decisions.

## Layout

```
src/mono_it_tax/
  config/      settings (.env), enums, constants, typed yearly rules       <- the root of everything
  domain/      pure logic: months, periods, payment, ledger, states, income, declaration, payment plan
  clients/     HTTP gateway (throttle, retry, error mapping), Monobank and NBU clients
  store/       encrypted per-year document, key providers (OS keyring / key file)
  services/    managers acting on the store and clients: fetch, marking, rates, accounts, reports
  copy/        user-facing Ukrainian texts: error catalog, declaration help, estimate
  pipelines/   orchestration of the steps (fetch, report); no math, no HTTP
  startup.py   composition root: builds clients, store, clock and services once
  api/         FastAPI app: routes, schemas, background job, account handles, launch-token auth
  launcher.py  `mono-it-tax`: picks a port, serves API + built UI, opens the browser
  errors.py    one error hierarchy with codes and params
  clock.py     the only place that touches real time
data/rules/    one reviewed YAML per tax year (rates, rows, deadlines, budget codes, sources)
web/           Vite + React + TypeScript wizard (cards -> period -> confirm -> fetch -> mark -> result)
tests/         unit, component, scenario, api, smoke (manual)
```

## Dependency direction

```
config -> domain -> clients | store -> services -> copy -> pipelines -> startup -> api -> launcher
```

Imports only point down this list (each layer may import the ones to its left). `import-linter`
enforces it (`uv run lint-imports`), and also forbids `domain` from importing I/O libraries.

## Why it is built this way

- **Rules are data, not code.** Rates, row numbers, deadlines and budget codes sit in
  `data/rules/<year>.yaml` with their sources and a `version`/`updated_on`. A new year is a new file;
  a year without a file is an error, never a guess. All user-visible strings live in `copy/` (backend)
  and `web/src/copy.ts` (UI).
- **The calendar month (Europe/Kyiv) is the unit of everything.** One bank request covers at most
  31 days + 1 hour, and a Kyiv month fits that, so one request is one account x one month. Tax dates
  are Kyiv days (a payment at 00:30 on 1 April is April, though still 31 March in UTC).
- **The fetch ledger is the source of truth for coverage.** What was *requested and answered* defines
  what is known, not which payments exist: an empty month fetched successfully is complete. A partly
  fetched month requests only the gap. Payments and the ledger record are written in one atomic
  document write, so coverage is never claimed without data.
- **Human decides, app informs.** Only incoming payments are stored. "Possible internal transfer" is a
  tag, never a filter. Results require every involved month to be confirmed ("done"); an unconfirmed
  month would silently count as zero income, so it is an error instead.
- **Exact money.** `Decimal` everywhere, one half-up rounding to kopiykas, bank integers in minor units.
  The declaration is cumulative: rows 13/24 come from rows 12/23 of the previous period, which is typed
  from the filed declaration (and validated against the rates) or computed from the stored income.
- **Fail loud.** Every error has a code and params; the user text is a catalog lookup (what the app tried,
  what happened, what to do next). Inputs outside the supported scope raise instead of producing a
  plausible number. Raw `httpx`/`yaml`/`json` errors never cross a layer.
- **Inject the world.** Clock, HTTP transport, key provider and rules are passed in, so tests run the real
  retry/throttle/parse code against a fake bank without waiting (the 60 s limit is virtual time).
- **Local-only by construction.** The server binds `127.0.0.1`, checks the `Host`, and needs a random
  per-launch token on every API call. Account ids stay in the backend (HMAC handles to the UI).
  The store is Fernet-encrypted; the key is kept outside `data/`.

## Tests

Layers, all deterministic and offline: **unit** (pure domain), **component** (clients over
`httpx.MockTransport`, store over `tmp_path`), **scenario** (whole flows through `startup` with a fake bank
and fake clock), **api** (`TestClient`). Property tests (`hypothesis`) cover month tiling, ledger
coverage and the declaration chain (Q1 -> H1 -> 9m -> year equals the one-shot cumulative result). A
test asserts that the declaration help is a faithful rendering of the state and of the rules file.
`tests/smoke` talks to the real services and is run by hand only.
