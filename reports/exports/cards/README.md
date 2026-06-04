# Credit-card statements go here

Drop your **credit-card** exports into this folder:

- **Isracard** — digital.isracard.co.il → פירוט חיובים → ייצוא
- **Cal** — cal-online.co.il → פירוט עסקאות → download `.xlsx`
- **Leumi card** — exported from the Leumi site

You can drop several files (e.g. one per card/person) — all of them are loaded.
The importer auto-detects the provider, so no renaming or tagging needed.

Then run from the project root:

```bash
python scripts/report.py
```

> The actual statement files (`*.xls` / `*.xlsx`) are git-ignored and never
> leave your machine. Only this README is tracked, to keep the folder in place.
