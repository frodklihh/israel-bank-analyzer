# Setup Guide for Israeli Bank Scrapers Bridge

This project uses `israeli-bank-scrapers` (npm) to scrape Israeli bank and credit card statements, wrapped via a Node.js bridge and called from Python.

## Prerequisites

- **Node.js 18+** (v24.16+ tested)
- **Python 3.10+** (3.14 tested, but see Python Setup section)
- **Chromium/Chrome browser** (Puppeteer will download automatically)

## Setup Steps

### 1. Install Node.js Dependencies

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

Create `.env` in the project root with your credentials:

```bash
# Bank Leumi          (USER = site username, PASSWORD = site password)
LEUMI_USER=<your_username>
LEUMI_PASSWORD=<your_password>

# Bank Hapoalim       (USER = userCode, PASSWORD = site password)
HAPOALIM_USER=<your_user_code>
HAPOALIM_PASSWORD=<your_password>

# Isracard            (needs THREE fields)
ISRACARD_USER=<your_id>          # Israeli ID (תעודת זהות)
ISRACARD_PASSWORD=<site_password> # Isracard website password
ISRACARD_CARD6=<last_6_digits>    # Last 6 digits of the card

# Visa Cal (if needed) (USER = site username, PASSWORD = site password)
# CAL_USER=<username>
# CAL_PASSWORD=<password>

# Email (optional)
SMTP_USER=<email@gmail.com>
SMTP_PASSWORD=<app_password>
EMAIL_TO=<recipient@example.com>
```

For **multi-user scenarios** (e.g., two families), use profile suffixes:

```bash
HAPOALIM_MIKHAIL_USER=mikhail_id
HAPOALIM_MIKHAIL_PASSWORD=mikhail_pass

HAPOALIM_DANIIL_USER=daniil_id
HAPOALIM_DANIIL_PASSWORD=daniil_pass

ISRACARD_MIKHAIL_USER=...
ISRACARD_MIKHAIL_PASSWORD=...
ISRACARD_MIKHAIL_CARD6=...
```

Then use: `python scripts/fetch.py --bank hapoalim:mikhail --cards isracard:mikhail`

## Quick Test

Test a single provider (bank automatically opens a browser for OTP entry if needed):

```bash
python scripts/test_bridge.py hapoalim:mikhail --start 2026-04-01
```

If OTP is required, enter it in the browser window that opens.

## Run Full Pipeline

Scrape all providers, categorize, build HTML report, and optionally email:

```bash
# Scrape for current month
python scripts/fetch.py --bank hapoalim:mikhail --cards isracard:mikhail

# For a specific month
python scripts/fetch.py --bank hapoalim:mikhail --cards isracard:mikhail --year 2026 --month 4

# With email
python scripts/fetch.py --bank hapoalim:mikhail --cards isracard:mikhail --email

# Cards only (skip bank)
python scripts/fetch.py --no-bank --cards isracard:mikhail isracard:daniil

# Hidden browser (--headless=true will not work with OTP)
python scripts/fetch.py --bank hapoalim:mikhail --cards isracard:mikhail --headless
```

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

## Supported Providers

| Provider name (CLI) | Kind | Credential fields | Notes |
|---------------------|------|-------------------|-------|
| **leumi** | Bank | `username` + `password` | |
| **hapoalim** | Bank | `userCode` + `password` | env `USER` holds the userCode |
| **isracard** | Cards | `id` + `password` + `card6Digits` | env `USER`=ID, `CARD6`=last 6 digits |
| **cal** | Cards | `username` + `password` | maps to scraper company `visaCal` |

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

1. Test with `scripts/test_bridge.py` for one provider
2. If successful, run `scripts/fetch.py` for full pipeline
3. Schedule with cron/Task Scheduler for automated monthly reports
