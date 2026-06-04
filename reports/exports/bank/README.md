# Bank statements go here

Drop your **bank account** exports into this folder:

- **Bank Leumi** — תנועות בחשבון → select range → export `.xls`
- **Bank Hapoalim** — עו"ש → ייצוא לאקסל

Both `.xls` and `.xlsx` work. The importer auto-detects the bank, so you
don't need to rename or tag files.

Then run from the project root:

```bash
python scripts/report.py
```

> The actual statement files (`*.xls` / `*.xlsx`) are git-ignored and never
> leave your machine. Only this README is tracked, to keep the folder in place.
