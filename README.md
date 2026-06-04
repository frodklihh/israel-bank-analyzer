# israel-bank-analyzer

A personal finance analyzer for Israeli banks and credit cards. It parses
exported `.xls`/`.xlsx` statements (or scrapes them automatically), auto-categorizes
every transaction, and generates a console + HTML report with an EN/RU toggle.

**Supported sources**

| Type | Providers |
|------|-----------|
| Bank accounts | Bank Leumi, Bank Hapoalim |
| Credit cards | Isracard, Cal, Leumi |

Owner name and national-ID numbers are scrubbed from descriptions before anything
is categorized, displayed, or emailed (see [Privacy](#privacy)).

---

## Installation

```bash
git clone https://github.com/frodklihh/israel-bank-analyzer.git
cd israel-bank-analyzer
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

> Requires **Python 3.11+**. The automatic-fetch path also needs Node.js
> (for the `israeli-bank-scrapers` bridge under `scraper/`).

---

## Two ways to build a report

### A. From files you downloaded yourself — `scripts/report.py`

**Simplest path** — the repo ships with two ready-made drop folders:

```
reports/exports/
├── bank/    ← put bank statements here   (Leumi / Hapoalim .xls/.xlsx)
└── cards/   ← put credit-card files here (Isracard / Cal / Leumi .xlsx)
```

Drop your downloads into the matching folder and run with **no arguments**:

```bash
python scripts/report.py
```

The importer auto-detects each file's provider, so you don't tag which bank it
came from. (Each folder has a short README; the statement files themselves are
git-ignored and never leave your machine.)

**Or point at any paths explicitly:**

```bash
# A whole folder at once (every .xls/.xlsx inside is loaded)
python scripts/report.py --bank-dir reports/exports/bank --cards-dir reports/exports/cards

# Explicit files
python scripts/report.py --bank reports/hapoalim.xlsx --cards reports/isracard.xlsx

# A focused period, or everything across all files
python scripts/report.py --cards-dir reports/exports/cards --year 2026 --month 5
python scripts/report.py --cards-dir reports/exports/cards --all

# Email the result (needs SMTP settings in .env)
python scripts/report.py --bank-dir ... --cards-dir ... --email
```

| Flag | Meaning |
|------|---------|
| `--bank FILE [FILE ...]` | Bank statement file(s) — Leumi/Hapoalim `.xls`/`.xlsx` |
| `--cards FILE [FILE ...]` | Credit-card file(s) — Isracard/Cal/Leumi `.xlsx` |
| `--bank-dir DIR [DIR ...]` | Load every `.xls`/`.xlsx` in a folder as bank statements |
| `--cards-dir DIR [DIR ...]` | Load every `.xls`/`.xlsx` in a folder as card files |
| `--year` / `--month` | Filter to a billing year / month (default: auto-detect dominant month) |
| `--all` | Count every transaction across all files, no period filter |
| `--email` | Send the HTML report by email |

> `--year` without `--month` produces a full-year report (every month, recurring
> charges summed). `--all` overrides `--year`/`--month`.

### B. Scrape automatically — `scripts/fetch.py`

Pulls statements straight from the providers via the `israeli-bank-scrapers`
bridge (no manual downloads), then builds the same report. Configure your bank
and card once in `.env` (copy [`.env.example`](.env.example)):

```ini
BANK_PROVIDER=hapoalim     # leumi | hapoalim
BANK_USER=...
BANK_PASSWORD=...

CARDS_PROVIDER=isracard    # isracard | cal | leumi
CARDS_USER=...
CARDS_PASSWORD=...
CARDS_CARD6=...            # Isracard only: last 6 digits of the card
```

Then just run — the provider comes from `.env`, so no flags are needed day-to-day:

```bash
python scripts/fetch.py                      # scrape configured bank + card
python scripts/fetch.py --no-bank            # cards only
python scripts/fetch.py --year 2026 --month 4 --email
```

> A visible browser opens so you can enter the OTP/2FA code; add `--headless` to hide it.

### Output

- **Console** — summary printed to stdout.
- **HTML report** — saved to `reports/<period>/report.html`, plus a fresh copy at
  `reports/report.html` so a bookmarked file never goes stale. EN/RU toggle built in.

---

## Where to download files (for path A)

| Source | Path on the website |
|--------|---------------------|
| Bank Leumi | תנועות בחשבון → select range → export `.xls` |
| Bank Hapoalim | עו"ש → ייצוא לאקסל |
| Isracard | digital.isracard.co.il → פירוט חיובים → ייצוא |
| Cal | cal-online.co.il → פירוט עסקאות → download `.xlsx` |

The importer auto-detects each file's format, so you don't tag which bank it came from.

---

## How categorization works

Transactions are tagged by keyword matching (`israel_bank_analyzer/categorizer.py`),
with a few amount-independent rules built for any user:

| Concept | Behaviour |
|---------|-----------|
| **Billing month** | 16→15 cycle (`core/period.py`): a purchase on/after the 16th counts toward the next billing month. |
| **Rent** | Checks (שיק) and rent-labelled payments (שכירות / שכ"ד) → House & Billing. The rent **amount is learned from the data** (a sum seen ≥2× as a check/label), so a month paid by an unlabelled transfer is caught too — nothing is hardcoded. |
| **Settlement detection** | Lump-sum card payments in the bank statement are excluded so card purchases aren't double-counted. |
| **Direct cards** | "MC דירקט"-type cards debit the bank instantly; their purchases are flagged `immediate` and never shown as pending. |
| **Pending vs. settled** | A card charge is *pending* if its billing month is later than the last bank-settled month. |

---

## Privacy

- `REDACT_NAMES` in `.env` — comma-separated tokens (the owner's name, noise tokens)
  stripped from descriptions. Whole-word match only.
- National-ID numbers (`מזהה 123456789`) are always removed automatically.
- Raw statements are git-ignored: `reports/*.xlsx`, `reports/**/*.xlsx`,
  `reports/exports_*/`, and generated reports never leave your machine.

---

## Project structure

```
israel-bank-analyzer/
├── israel_bank_analyzer/  # Categorization rules + PII redaction
│   ├── categorizer.py     # Keyword rules, rent/direct-card logic
│   └── privacy.py         # Owner-name / national-ID scrubbing
├── core/                  # Business logic
│   ├── analytics.py       # Report calculations (income, expenses, pending)
│   └── period.py          # Billing-month logic (16→15 cycle)
├── scripts/               # CLI entry points
│   ├── report.py          # Build a report from downloaded files
│   ├── fetch.py           # Scrape providers → report → email
│   └── importer.py        # File parser (Leumi/Hapoalim/Isracard/Cal)
├── fetcher/               # Node israeli-bank-scrapers bridge wrapper
│   └── scraper_bridge.py
├── scraper/               # Node.js bridge (israeli-bank-scrapers)
├── config/                # Credential & email config from .env
│   └── settings.py
├── notifier/              # Email delivery
│   └── email.py
├── views/                 # Presentation
│   ├── console.py         # Terminal output
│   └── html.py            # HTML via Jinja2
├── templates/
│   └── report.html        # HTML template with JS translation
├── tests/                 # pytest suite
└── reports/               # Generated reports + input drop folders
    └── exports/           #   bank/ and cards/ — drop statements here
```

---

## Development

```bash
# Run the test suite (scope to tests/ so pytest doesn't scan site-packages)
python -m pytest tests/
```
