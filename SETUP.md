# Setup Guide for Israeli Bank Scrapers Bridge

This project pulls Israeli bank and credit-card statements two ways:

- **`scripts/fetch.py`** — live scraping via the [`israeli-bank-scrapers`](https://www.npmjs.com/package/israeli-bank-scrapers) npm package, wrapped in a Node.js bridge and called from Python. No file downloads.
- **`scripts/report.py`** — build the same report from statement files you downloaded by hand (`.xls`/`.xlsx`). Use this when the scrapers are blocked.

Both paths categorize the transactions and produce an HTML report (and can email it).

## Prerequisites

- **Node.js 18+** (v24.16+ tested) — only required for `scripts/fetch.py`
- **Python 3.10+** (3.14 tested, but see Python Setup section)
- **Chromium/Chrome browser** (Puppeteer will download automatically)

## Setup Steps

### 1. Install Node.js Dependencies

Only needed for live scraping (`scripts/fetch.py`). Skip if you only use `scripts/report.py`.

```bash
cd scraper/
npm install
npx puppeteer browsers install chrome@126  # Install Chrome 126 (required by the package)
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
# If pip is missing:
#   python -m pip install --upgrade pip
#   python get-pip.py
```

### 3. Environment Variables

Copy the template and fill in your own values:

```bash
cp .env.example .env          # PowerShell: Copy-Item .env.example .env
```

Credentials are only needed for the **automatic scraper** (`scripts/fetch.py`). If you
download statements yourself and use `scripts/report.py`, you can leave them blank.

One install belongs to **one user**: one bank (`BANK_*`) plus one card issuer (`CARDS_*`).
Pick each provider with `BANK_PROVIDER` / `CARDS_PROVIDER`.

```bash
# ── Your bank account ─────────────────────────────────────────────
# BANK_PROVIDER: one of  leumi | hapoalim
BANK_PROVIDER=hapoalim
# BANK_USER:  Leumi → site username   |   Hapoalim → userCode
BANK_USER=<your_username_or_usercode>
BANK_PASSWORD=<your_password>

# ── Your credit card ──────────────────────────────────────────────
# CARDS_PROVIDER: one of  isracard | cal | leumi
CARDS_PROVIDER=isracard
# CARDS_USER:  Isracard → Israeli ID (ת"ז)   |   Cal/Leumi → site username
CARDS_USER=<your_id_or_username>
CARDS_PASSWORD=<your_password>
# CARDS_CARD6:  Isracard only — last 6 digits of the card
CARDS_CARD6=<last_6_digits>
```

Notes:
- **`CARD6` is Isracard-only.** Leave it blank for Cal/Leumi. (A symmetric
  `BANK_CARD6` exists in the config but no current bank provider needs it.)
- All `BANK_*` and `CARDS_*` values are read by `config/settings.py`; missing a
  required one raises a clear "Missing required env var" error.

#### Privacy (optional)

```bash
# Comma-separated tokens stripped from transaction descriptions (whole-word match),
# e.g. the account owner's name that the bank embeds in the "purpose" field.
# National-ID / order / account numbers are always removed automatically.
REDACT_NAMES=<surname>,<firstname>
```

#### Email (optional — only needed for the `--email` flag)

```bash
SMTP_HOST=smtp.gmail.com   # default
SMTP_PORT=587              # default
SMTP_USER=you@gmail.com    # login for the SMTP server
SMTP_PASSWORD=<app_password>   # app password, NOT your normal account password
EMAIL_FROM=                # "From" address; defaults to SMTP_USER if empty
EMAIL_TO=                  # recipient; defaults to the sender (sends to yourself)
```

## Running the Analyzer

### Option A — Automatic scraping (`scripts/fetch.py`)

Which bank/card to scrape comes from `.env` (`BANK_PROVIDER` + `CARDS_PROVIDER` and
their credentials), so day-to-day you just run the script with no provider arguments:

```bash
# Scrape configured bank + card for the current billing month
python scripts/fetch.py

# A specific month
python scripts/fetch.py --year 2026 --month 4

# With email (requires SMTP_* env vars)
python scripts/fetch.py --email

# Cards only (skip the bank)
python scripts/fetch.py --no-bank

# Bank only (skip the card)
python scripts/fetch.py --no-cards

# Hidden browser — note: OTP/SMS challenges can't be answered when hidden
python scripts/fetch.py --headless
```

The browser is **visible by default** so you can complete any SMS/OTP challenge in
the window that opens. Output is written to `reports/<year>-<month>/report.html`.

### Option B — From downloaded statement files (`scripts/report.py`)

When the scrapers are blocked, download statements from the bank/card websites and
feed the files to `report.py`. The loader auto-detects each file's format
(bank statement vs Isracard/Cal/Leumi card), so you don't have to tell it which is which.

The simplest path: drop your statements into the ready-made folders and run with no
arguments —

```
reports/exports/bank/    ← bank statements (Leumi / Hapoalim)
reports/exports/cards/   ← credit cards   (Isracard / Cal / Leumi)
```

```bash
# Loads both default drop folders above
python scripts/report.py

# Explicit files
python scripts/report.py --bank exports/hapoalim.xlsx --cards exports/isracard.xlsx
python scripts/report.py --bank exports/leumi.xls --cards exports/cal1.xlsx exports/cal2.xlsx

# Whole folders (every .xls/.xlsx inside is loaded)
python scripts/report.py --bank-dir exports/bank --cards-dir exports/cards

# ONE mixed folder — each file is auto-classified as bank vs card by its format.
# Recurses into subfolders, so a flat folder OR a bank/ + cards/ split both work
# in a single command.
python scripts/report.py --dir exports/me/

# Period control
python scripts/report.py --year 2026 --month 5   # one month
python scripts/report.py --year 2026             # full-year report (every month)
python scripts/report.py --all                   # every transaction, no period filter

# Email the result
python scripts/report.py --dir exports/me/ --email
```

Where to download files:

| Provider | Path on the website |
|----------|---------------------|
| Hapoalim | https://www.bankhapoalim.co.il → עו"ש → ייצוא לאקסל |
| Isracard | https://digital.isracard.co.il → פירוט חיובים → ייצוא |
| Leumi    | https://www.leumi.co.il → תנועות בחשבון → ייצוא |
| Cal      | https://www.cal-online.co.il → פירוט חיובים → ייצוא |

Output is written to `reports/<period>/report.html`, and a stable copy is always
refreshed at `reports/report.html`.

## Quick Test

1. **Confirm the install** by running the unit tests (they need no credentials and no
   network). Tests use the project's virtualenv interpreter:

   ```bash
   .venv/Scripts/python.exe -m pytest tests/    # Windows
   # or, with the venv activated:
   python -m pytest tests/
   ```

   You should see all tests pass.

2. **Smoke-test live scraping** with a single source, so you only validate one set of
   credentials + the Node bridge at a time. The browser opens visibly — enter the
   OTP there if prompted:

   ```bash
   python scripts/fetch.py --no-cards     # bank only
   # or
   python scripts/fetch.py --no-bank      # cards only
   ```

   A non-zero transaction count and a saved `reports/<year>-<month>/report.html`
   means the bridge and credentials work.

## Troubleshooting

### Chrome/Puppeteer Issues on Windows

**Symptom:** `Could not find Chrome (ver. 126.0.6478.126)`

**Fix:**
```bash
rm -rf ~/.cache/puppeteer/chrome
cd scraper && npx puppeteer browsers install chrome@126
```

If that doesn't work, try **WSL2 or Docker** (Puppeteer works more reliably there):

```bash
# WSL2 / Linux
wsl -d Ubuntu
cd /mnt/d/MyProjects/leumi-analyzer
python scripts/fetch.py ...
```

### Python Module Not Found

```bash
# Reinstall pip if missing
python -m pip install --upgrade pip --force-reinstall
pip install -r requirements.txt
```

### Hebrew/Unicode Output Not Displaying

The Node bridge outputs progress messages in Hebrew. On Windows console, this may show garbled text but doesn't affect the JSON parsing. The actual transaction data is always UTF-8 encoded and works correctly.

## Architecture

```
scripts/fetch.py (Python entry point)
  ↓
fetcher/scraper_bridge.py (Python wrapper)
  ↓
subprocess → scraper/bridge.js (Node.js JSON bridge)
  ↓
israeli-bank-scrapers npm package (Puppeteer + login automation)
  ↓
Bank/Card website (Hapoalim, Isracard, Leumi, Cal)
  ↓
JSON result → Python conversion → list[Transaction]
  ↓
categorize → build_report → HTML + email
```

`scripts/report.py` reuses the same back half of the pipeline
(`load_file → categorize → build_report → HTML + email`), but reads downloaded
files instead of scraping.

## Supported Providers

| Provider | Kind | `BANK_*` / `CARDS_*` fields | Notes |
|----------|------|-----------------------------|-------|
| **leumi**    | Bank | `USER` (site username) + `PASSWORD` | |
| **hapoalim** | Bank | `USER` (userCode) + `PASSWORD` | `BANK_USER` holds the userCode |
| **isracard** | Cards | `USER` (Israeli ID) + `PASSWORD` + `CARD6` (last 6 digits) | only provider needing `CARD6` |
| **cal**      | Cards | `USER` (site username) + `PASSWORD` | maps to scraper company `visaCal` |
| **leumi**    | Cards | `USER` (site username) + `PASSWORD` | Leumi-issued cards |

Login is performed automatically by `israeli-bank-scrapers` using the credentials
above. If a provider triggers an SMS/OTP challenge, complete it in the browser
window (run without `--headless` so the window is visible).

## Old Playwright Fetchers (removed)

The old custom Playwright fetchers have been removed in favour of the Node
`israeli-bank-scrapers` bridge. Provider/credential wiring now lives entirely in
`fetcher/scraper_bridge.py` (`PROVIDERS`). The `playwright` dependency has been
dropped from `requirements.txt`. If you need the old browser-automation code,
recover it from git history.

## Next Steps

1. Run `python -m pytest tests/` to confirm the install.
2. Smoke-test one source with `python scripts/fetch.py --no-cards` (or `--no-bank`),
   or build a report from a downloaded file with `python scripts/report.py --dir ...`.
3. Schedule `scripts/fetch.py` with cron/Task Scheduler for automated monthly reports.
