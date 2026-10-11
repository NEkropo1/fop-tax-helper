# fop-tax-helper

A local, human-in-the-loop helper for Ukrainian sole proprietors (ФОП, single-tax **group 3**) who
receive income on Monobank. It pulls your incoming payments, lets **you** decide which of them are
taxable income, converts foreign currency with the official NBU rates, and tells you exactly what to
type into the tax declaration (F0103309) and what to pay: single tax (ЄП), military levy (ВЗ) and the
minimum social contribution (ЄСВ), with deadlines.

It does **not** file anything and does **not** pay anything: you do both yourself in the
[taxpayer cabinet](https://cabinet.tax.gov.ua/). It only saves you the counting and the guesswork.

> Not tax advice. Rates and rules change; they live in one reviewed file per year
> ([`data/rules/2026.yaml`](data/rules/2026.yaml)) with their sources. Check the numbers against the
> cabinet and the current legislation ([Tax Code](https://zakon.rada.gov.ua/laws/show/2755-17),
> [tax service](https://tax.gov.ua/)) before filing, and ask an accountant when in doubt.

## What it does

1. Shows your Monobank accounts (cards and ФОП accounts). Pick one or several.
2. You choose a **tax period** (Q1, half-year, 9 months, year) or any months of one year.
3. It tells you how many bank requests that needs (Monobank allows 1 per minute) and fetches only what
   is missing. Every answer is saved at once, so an interrupted fetch just continues.
4. You see every incoming payment with all bank fields and tick the ones that are income
   (Shift+click selects a range, an amount can be corrected). Payments that look like transfers
   between your own cards are only *tagged*, never hidden. You confirm each month as done.
5. Result: an indicative estimate, and (optionally) step-by-step help for the declaration: which
   rows to check, what to type, which rows the cabinet fills itself, and what to pay by when.
   The previous period comes either from the rows of your filed declaration (typed in) or is computed
   from your bank data.

Scope on purpose: group 3 at 5% (3% VAT payers use another row, set in the rules file), no employees,
no 15% income, no amended declarations. Anything outside that raises a clear error instead of a
plausible wrong number.

## Quick start

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 20.19+ (or 22+).

```bash
git clone git@github.com:NEkropo1/fop-tax-helper.git
cd fop-tax-helper
uv sync
npm --prefix web install
npm --prefix web run build        # builds the UI into web/dist
cp .env.example .env              # then put your token into .env
uv run mono-it-tax
```

The browser opens at `http://127.0.0.1:<port>/#token=...`. The one-time key in the link is what lets
the page talk to the app. Stop with Ctrl+C.

### Getting the Monobank token

1. Open <https://api.monobank.ua/> and sign in with the Monobank app.
2. Activate **«Токен фізичної особи та ФОП»** and copy it immediately (it is shown once).
3. Put it into `.env` as `MONOBANK_TOKEN=...`.

No developer registration is needed: the personal API is meant for exactly this use. Without a token the
page explains these steps itself.

### Settings (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `MONOBANK_TOKEN` | – | personal token (required) |
| `DATA_DIR` | `data` | where the encrypted store and logs live |
| `KEY_STORAGE` | `auto` | encryption key in the OS keyring (`keyring`), a key file (`file`) or either (`auto`) |
| `HTTP_TIMEOUT_S`, `RETRY_ATTEMPTS`, `RETRY_BACKOFF_S` | 30 / 3 / 2 | network behaviour |

## Privacy and security

- Everything runs on your machine. The only outside calls are `api.monobank.ua` (with your token) and
  `bank.gov.ua` (public NBU rates). No telemetry.
- Fetched data is stored **encrypted** (Fernet) in `data/store/<year>.enc`. The key lives in the OS
  credential store, or in a key file in your user config folder (owner-only permissions on Linux/macOS), never next to the data. This
  protects copied files (backups, synced folders), not an attacker already logged in as you.
- The token stays in `.env` (plain text, git-ignored). Account ids and IBANs never reach the
  browser, only opaque handles and masked card numbers.
- The local server listens on `127.0.0.1` only and requires a per-launch key on every request.
- Nothing is deleted automatically; **«Мої дані»** deletes a year or everything after an explicit confirmation.

## Development

```bash
uv run ruff format src tests && uv run ruff check src tests --fix
uv run mypy src tests
uv run lint-imports                    # layer contract
uv run pytest                          # unit, component, scenario, API; coverage gate 95%
npm --prefix web test                  # UI logic tests
uv run pytest -m smoke -o addopts=""   # real services, run by hand only
```

How the code is organised and why: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Коротко українською

Локальний помічник для ФОП 3 групи з доходом на Monobank: завантажує надходження, ви самі позначаєте,
що є оподатковуваним доходом, застосунок переводить валюту за курсом НБУ та підказує, що саме вписати в
декларацію (F0103309) і що сплатити (ЄП, ВЗ, ЄСВ) із датами. Нічого не подає і не сплачує за вас. Дані
лишаються на вашому комп'ютері й зберігаються зашифрованими. Запуск: `uv sync`, `npm --prefix web install`,
`npm --prefix web run build`, токен у `.env`, `uv run mono-it-tax`. Це не податкова консультація.

## License

MIT, see [LICENSE](LICENSE).

## Contact

Found something outdated or wrong? Write on
[LinkedIn](https://www.linkedin.com/in/paul-savchuk-ne/) or open an issue on
[GitHub](https://github.com/NEkropo1/fop-tax-helper).
