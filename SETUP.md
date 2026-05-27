# Setup Guide for Israeli Bank Scrapers Bridge

This project uses `israeli-bank-scrapers` (npm) to scrape Israeli bank and credit card statements, wrapped via a Node.js bridge and called from Python.

## Quick Start with Docker (Recommended)

Docker handles all dependencies (Python, Node.js, Chrome) in one clean container.

### Prerequisites
- Docker and Docker Compose installed

### 1. Copy environment template
```bash
cp .env.example .env
```
Edit `.env` with your credentials (see [Environment Variables](#environment-variables) section below).

### 2. Build and run
```bash
# Build the Docker image (first time only, ~10 min)
docker-compose build

# Run scraper for current month
docker-compose run --rm scraper --bank hapoalim:mikhail --cards isracard:mikhail

# For specific month
docker-compose run --rm scraper --bank hapoalim:mikhail --cards isracard:mikhail --year 2026 --month 4

# With email
docker-compose run --rm scraper --bank hapoalim:mikhail --cards isracard:mikhail --email

# View help
docker-compose run --rm scraper --help
```

Reports will be saved to `./reports/` on your host machine.

### Scheduled runs (Linux/Mac with cron)
```bash
# Add to crontab (runs on 1st of every month at 9am)
0 9 1 * * cd /path/to/leumi-analyzer && docker-compose run --rm scraper --bank hapoalim:mikhail --cards isracard:mikhail --email
```

---

## Manual Setup (Linux / WSL / macOS)

If you prefer not to use Docker:

### Prerequisites

- **Node.js 18+** (v24.16+ tested)
- **Python 3.10+** (3.11+ recommended)
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
# Bank Leumi
LEUMI_USER=<your_username>
LEUMI_PASSWORD=<your_password>

# Bank Hapoalim
HAPOALIM_USER=<your_username>
HAPOALIM_PASSWORD=<your_password>

# Isracard
ISRACARD_USER=<your_id>           # Israeli ID
ISRACARD_PASSWORD=<last_4_digits>  # Last 4 digits of any card

# Visa Cal (if needed)
# CAL_USER=<id>
# CAL_PASSWORD=<last_4_digits>

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

| Provider | Kind | Login |  OTP | Notes |
|----------|------|-------|------|-------|
| **Leumi** | Bank | User+Pass | SMS | SMS required |
| **Hapoalim** | Bank | User+Pass | OTP | OTP via SMS/phone |
| **Isracard** | Cards | ID + 4 digits | SMS | SMS required |
| **Cal (Visa Cal)** | Cards | ID + 4 digits | OTP | OTP via SMS |

All providers require manual OTP entry in the browser window (cannot be automated for security reasons).

## Old Playwright Fetchers

The old custom Playwright fetchers (`fetcher/hapoalim.py`, `fetcher/isracard.py`, etc.) are no longer used. They can be deleted once this setup is confirmed working.

Files that can be deleted:
- `fetcher/hapoalim.py`
- `fetcher/isracard.py`
- `fetcher/leumi.py`
- `fetcher/cal.py`
- `fetcher/session.py`
- `fetcher/base.py`
- `fetcher/registry.py` (old registry, replaced by internal `scraper_bridge.PROVIDERS`)

## Next Steps

1. Test with `scripts/test_bridge.py` for one provider
2. If successful, run `scripts/fetch.py` for full pipeline
3. Schedule with cron/Task Scheduler for automated monthly reports
