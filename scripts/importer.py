"""
importer.py - parser for Bank Leumi export files

Leumi exports:
- .xls  -> HTML tables (bank statement)
- .xlsx -> two formats: bank statement or credit card transactions
"""

import re
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import math


@dataclass
class Transaction:
    date: datetime
    description: str
    reference: str
    debit: float
    credit: float
    balance: float
    source: str = ""
    category: str = ""

    def __post_init__(self) -> None:
        # Scrub owner name + national-ID from free-text fields at the single
        # point every parser (and the scraper bridge) funnels through, so PII
        # never reaches categorization, the HTML report, or email.
        # Imported lazily to avoid a circular import via leumi_analyzer/__init__.
        from leumi_analyzer.privacy import redact_pii

        self.description = redact_pii(self.description)
        self.reference = redact_pii(self.reference)


def _parse_amount(s) -> float:
    """Convert '₪5,403.92' or NaN to a float."""
    if s is None:
        return 0.0
    try:
        if isinstance(s, float) and math.isnan(s):
            return 0.0
    except (TypeError, ValueError):
        pass
    cleaned = str(s).replace("₪", "").replace(",", "").replace(" ", "").strip()
    if not cleaned or cleaned.lower() == "nan":
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _is_refund(description: str) -> bool:
    refund_words = [
        "זיכוי", "החזר", "refund", "credit", "rebate", "cashback", "return", "voucher"
    ]
    desc_lower = (description or "").lower()
    return any(word.lower() in desc_lower for word in refund_words)


def parse_leumi_xls(path: str | Path) -> list[Transaction]:
    """Parse Leumi .xls (HTML) bank statement."""
    from bs4 import BeautifulSoup

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    soup = BeautifulSoup(content, "html.parser")
    tables = soup.find_all("table")

    if not tables:
        return []

    data_table = tables[-1]
    rows = data_table.find_all("tr")
    transactions = []

    for row in rows:
        cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
        if len(cells) < 7:
            continue
        if not re.match(r"\d{2}/\d{2}/\d{4}", cells[0]):
            continue

        try:
            date = datetime.strptime(cells[0], "%d/%m/%Y")
            transactions.append(Transaction(
                date=date,
                description=cells[2],
                reference=cells[3],
                debit=_parse_amount(cells[4]),
                credit=_parse_amount(cells[5]),
                balance=_parse_amount(cells[6]),
                source="bank",
            ))
        except (ValueError, IndexError):
            continue

    return transactions


def parse_leumi_bank_xlsx(path: str | Path) -> list[Transaction]:
    """Parse Leumi bank statement exported as .xlsx.

    Dynamically locates the header row since Leumi exports include
    metadata rows at the top of the file.

    Expected columns (row 5 in a typical export):
        תאריך | הפעולה | פרטים | אסמכתא | חובה | זכות | יתרה בש''ח | תאריך ערך | לטובת | עבור
    """
    import pandas as pd

    df_raw = pd.read_excel(path, header=None)
    header_row_idx = 4

    for idx, row in df_raw.iterrows():
        row_str = " ".join(str(v) for v in row.values)
        if "תאריך" in row_str and ("יתרה" in row_str or "חובה" in row_str):
            header_row_idx = idx
            break

    df = pd.read_excel(path, header=header_row_idx)
    df.columns = [str(c).strip() for c in df.columns]

    date_col = next((c for c in df.columns if c == "תאריך"), next((c for c in df.columns if "תאריך" in c), df.columns[0]))
    desc_col = next((c for c in df.columns if c in ("הפעולה", "תיאור")), df.columns[1] if len(df.columns) > 1 else df.columns[0])
    ref_col = next((c for c in df.columns if "אסמכתא" in c), None)
    debit_col = next((c for c in df.columns if "חובה" in c), None)
    credit_col = next((c for c in df.columns if "זכות" in c), None)
    balance_col = next((c for c in df.columns if "יתרה" in c), None)
    purpose_col = next((c for c in df.columns if c == "עבור"), None)

    transactions = []
    for _, row in df.iterrows():
        try:
            date_raw = row[date_col]
            if pd.isna(date_raw) or str(date_raw).strip() == "" or "תאריך" in str(date_raw):
                continue

            if isinstance(date_raw, datetime):
                date = date_raw
            else:
                date = pd.to_datetime(date_raw, dayfirst=True).to_pydatetime()

            description = str(row[desc_col]).strip() if not pd.isna(row[desc_col]) else ""
            if not description or description.lower() == "nan":
                continue

            if purpose_col and purpose_col in row.index:
                purpose = row[purpose_col]
                if purpose is not None and not pd.isna(purpose):
                    purpose_str = str(purpose).strip()
                    if purpose_str and purpose_str.lower() != "nan":
                        description = f"{description} {purpose_str}"

            reference = str(row[ref_col]).strip() if ref_col and ref_col in row and not pd.isna(row[ref_col]) else ""
            debit = _parse_amount(row[debit_col]) if debit_col and debit_col in row else 0.0
            credit = _parse_amount(row[credit_col]) if credit_col and credit_col in row else 0.0
            balance = _parse_amount(row[balance_col]) if balance_col and balance_col in row else 0.0

            transactions.append(Transaction(
                date=date.replace(tzinfo=None),
                description=description,
                reference=reference,
                debit=debit,
                credit=credit,
                balance=balance,
                source="bank",
            ))
        except Exception:
            continue

    return transactions


def parse_leumi_credit_card(path: str | Path) -> list[Transaction]:
    """Parse Leumi credit card transactions xlsx.

    Column layout (header on row 1):
        0: date, 1: merchant name, 2: amount, 3: card, ...
    """
    import pandas as pd

    df = pd.read_excel(path, header=1)
    transactions = []

    for _, row in df.iterrows():
        try:
            date_raw = row.iloc[0]
            description = str(row.iloc[1]).strip()
            amount_raw = row.iloc[2]

            if str(date_raw) == "nan" or str(amount_raw) == "nan" or description == "nan":
                continue

            date = pd.to_datetime(date_raw).to_pydatetime().replace(tzinfo=None)
            amount = float(str(amount_raw).replace(",", ""))

            if _is_refund(description):
                debit = 0.0
                credit = abs(amount)
            else:
                debit = amount if amount > 0 else 0.0
                credit = abs(amount) if amount < 0 else 0.0

            transactions.append(Transaction(
                date=date,
                description=description,
                reference="",
                debit=debit,
                credit=credit,
                balance=0.0,
                source="credit_card",
            ))
        except (ValueError, TypeError):
            continue

    return transactions


def parse_isracard_xlsx(path: str | Path) -> list[Transaction]:
    """Parse Isracard xlsx export.

    The file has metadata rows at top, then one or more sections each preceded
    by a column-header row starting with 'תאריך רכישה'.
    The billing amount in ILS is in column 'סכום חיוב' (index 4).
    """
    import pandas as pd

    df = pd.read_excel(path, header=None)
    transactions: list[Transaction] = []
    reading = False

    for _, row in df.iterrows():
        cells = [str(v).strip() for v in row.values]
        first = cells[0]

        if first == "תאריך רכישה":
            reading = True
            continue

        if not reading:
            continue

        if not first or first == "nan":
            reading = False
            continue

        try:
            date = pd.to_datetime(first, format="%d.%m.%y").to_pydatetime()
        except (ValueError, TypeError):
            reading = False
            continue

        description = cells[1] if len(cells) > 1 and cells[1] != "nan" else ""
        reference = cells[6] if len(cells) > 6 and cells[6] != "nan" else ""
        amount = _parse_amount(cells[4]) if len(cells) > 4 else 0.0

        debit = amount if amount > 0 else 0.0
        credit = abs(amount) if amount < 0 else 0.0

        transactions.append(Transaction(
            date=date.replace(tzinfo=None),
            description=description,
            reference=reference,
            debit=debit,
            credit=credit,
            balance=0.0,
            source="isracard",
        ))

    return transactions


def parse_hapoalim_xlsx(path: str | Path) -> list[Transaction]:
    """Parse Bank Hapoalim Excel export.

    Hapoalim exports have Hebrew headers like:
        תאריך | תאור | אסמכתא | חובה | זכות | יתרה
    The header row may not be the first row.
    """
    import pandas as pd

    df_raw = pd.read_excel(path, header=None)
    header_row_idx = 0

    for idx, row in df_raw.iterrows():
        row_str = " ".join(str(v) for v in row.values)
        if "תאריך" in row_str and ("תאור" in row_str or "תיאור" in row_str):
            header_row_idx = idx
            break

    df = pd.read_excel(path, header=header_row_idx)
    df.columns = [str(c).strip() for c in df.columns]

    date_col = next((c for c in df.columns if "תאריך" in c), df.columns[0])
    desc_col = next((c for c in df.columns if "תאור" in c or "תיאור" in c), df.columns[1])
    ref_col = next((c for c in df.columns if "אסמכתא" in c), None)
    debit_col = next((c for c in df.columns if "חובה" in c), None)
    credit_col = next((c for c in df.columns if "זכות" in c), None)
    balance_col = next((c for c in df.columns if "יתרה" in c), None)

    transactions = []
    for _, row in df.iterrows():
        try:
            date_raw = row[date_col]
            if pd.isna(date_raw) or str(date_raw).strip() == "" or "תאריך" in str(date_raw):
                continue

            if isinstance(date_raw, datetime):
                date = date_raw
            else:
                date = pd.to_datetime(date_raw, dayfirst=True).to_pydatetime()

            description = str(row[desc_col]).strip() if not pd.isna(row[desc_col]) else ""
            if not description or description.lower() == "nan":
                continue

            reference = str(row[ref_col]).strip() if ref_col and not pd.isna(row.get(ref_col)) else ""
            debit = _parse_amount(row[debit_col]) if debit_col and debit_col in row else 0.0
            credit = _parse_amount(row[credit_col]) if credit_col and credit_col in row else 0.0
            balance = _parse_amount(row[balance_col]) if balance_col and balance_col in row else 0.0

            transactions.append(Transaction(
                date=date.replace(tzinfo=None),
                description=description,
                reference=reference,
                debit=debit,
                credit=credit,
                balance=balance,
                source="bank",
            ))
        except Exception:
            continue

    return transactions


def load_file(path: str | Path) -> list[Transaction]:
    """Auto-detect file format and parse accordingly."""
    import pandas as pd

    path = Path(path)

    if path.suffix.lower() == ".xlsx":
        df = pd.read_excel(path, header=None, nrows=12)
        all_text = " ".join(str(v) for row in df.itertuples(index=False) for v in row)

        if "תאריך רכישה" in all_text:
            return parse_isracard_xlsx(path)

        # Hapoalim markers: "תאור" (not "תיאור") or "פועלים" in metadata
        hapoalim_markers = ["הפועלים", "פועלים", "Hapoalim"]
        if any(m in all_text for m in hapoalim_markers):
            return parse_hapoalim_xlsx(path)

        bank_markers = ["יתרה", "חובה", "תנועות בחשבון", "מסגרת האשראי"]
        if any(m in all_text for m in bank_markers):
            # Could be Leumi or generic bank format — try Hapoalim if "תאור"
            if "תאור" in all_text and "תיאור" not in all_text:
                return parse_hapoalim_xlsx(path)
            return parse_leumi_bank_xlsx(path)

        return parse_leumi_credit_card(path)

    return parse_leumi_xls(path)