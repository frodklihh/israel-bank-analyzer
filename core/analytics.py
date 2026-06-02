from datetime import datetime
from dataclasses import dataclass, field
from scripts.importer import Transaction
from core.period import billing_month

UNKNOWN_CATEGORY = "❓ Other"

FEE_KEYWORDS = [
    "עמלה", "עמלת", "עמלות", "דמי ניהול", "מסלול בסיסי",
    "עמ.הקצאת אשראי", "עמל.ערוץ יש", "דמי כרטיס"
]

CC_REFUND_KEYWORDS = [
    "כרטיסי אשראי", "כרטיס אשראי", "כ' אשראי", "ויזה",
    "visa", "isracard", "cal", "max",
]


@dataclass
class CategorySummary:
    name: str
    total: float
    transactions: list[Transaction]


@dataclass
class MonthSummary:
    label: str
    income: float
    expenses: float
    net: float
    categories: list[CategorySummary]


@dataclass
class ReportData:
    period_label: str

    opening_balance: float
    closing_balance: float
    balance_change: float

    total_income: float
    total_expenses: float
    real_net: float

    pending_cc: float
    pending_transactions: list[Transaction]

    past_settlements: float = 0.0
    past_settlement_transactions: list[Transaction] = field(default_factory=list)

    categories: list[CategorySummary] = field(default_factory=list)
    income_transactions: list[Transaction] = field(default_factory=list)
    monthly_breakdown: list[MonthSummary] = field(default_factory=list)


def filter_transactions(transactions: list[Transaction], year: int = None, month: int = None) -> list[Transaction]:
    filtered = []
    for tx in transactions:
        bm = billing_month(tx.date)
        if year and bm.year != year:
            continue
        if month and bm.month != month:
            continue
        filtered.append(tx)
    return filtered


def is_credit_card_settlement(tx: Transaction) -> bool:
    """Bank line that pays off the credit card (one lump sum)."""
    if tx.source != "bank" or tx.debit == 0:
        return False

    desc = tx.description.lower()
    if "דמי כרטיס" in desc or "עמלת כרטיס" in desc:
        return False

    cc_keywords = [
        "חיוב כרטיס", "חיוב כרטיסי", "כרטיסי אשראי", "כרטיס אשראי", "חיובי כרטיס",
        "לאומי קארד", "ישראכרט", "מקס", "כאל", "אמקס", "אמריקן אקספרס",
        "מסטרקארד", "מסטרקרד", "כ' אשראי",
        "leumi card", "isracard", "max", "cal", "visa", "ויזה", "mastercard", "amex",
        "הוראת קבע מקס", "הוראת קבע ישראכרט", "חיובי קרדיט",
    ]
    return any(kw in desc for kw in cc_keywords)


def is_bank_fee(tx: Transaction) -> bool:
    """Bank service fees (card fee, account maintenance, etc)."""
    if tx.source != "bank" or tx.debit == 0:
        return False
    return any(kw in tx.description for kw in FEE_KEYWORDS)


def is_cc_refund(tx: Transaction) -> bool:
    """Credit on bank account that's actually a credit card refund (not real income)."""
    if tx.source != "bank" or tx.credit <= 0:
        return False
    desc = tx.description.lower()
    return any(kw in desc for kw in CC_REFUND_KEYWORDS)


def build_report(
    bank_txs_all: list[Transaction],
    card_txs_all: list[Transaction],
    year: int = None,
    month: int = None,
) -> ReportData:
    bank_txs = filter_transactions(bank_txs_all, year=year, month=month)
    card_txs = filter_transactions(card_txs_all, year=year, month=month)

    # ----- Opening / closing balance -----
    if bank_txs:
        newest_first = True
        for i in range(len(bank_txs) - 1):
            tx_first = bank_txs[i]
            tx_second = bank_txs[i + 1]
            if abs(tx_first.balance - (tx_second.balance + tx_first.credit - tx_first.debit)) < 0.01:
                if tx_first.credit != 0 or tx_first.debit != 0:
                    newest_first = True
                    break
            if abs(tx_second.balance - (tx_first.balance + tx_second.credit - tx_second.debit)) < 0.01:
                if tx_second.credit != 0 or tx_second.debit != 0:
                    newest_first = False
                    break

        indexed_bank = list(enumerate(bank_txs))
        if newest_first:
            indexed_bank.sort(key=lambda x: (x[1].date, -x[0]))
        else:
            indexed_bank.sort(key=lambda x: (x[1].date, x[0]))

        sorted_bank = [tx for _, tx in indexed_bank]
        closing_balance = sorted_bank[-1].balance

        first_period_date = sorted_bank[0].date
        prev_txs = [tx for tx in bank_txs_all if tx.date < first_period_date]
        if prev_txs:
            last_day = max(tx.date for tx in prev_txs)
            same_day_txs = [tx for tx in prev_txs if tx.date == last_day]
            opening_balance = min(tx.balance for tx in same_day_txs)
        else:
            opening_balance = sorted_bank[0].balance - sorted_bank[0].credit + sorted_bank[0].debit
    else:
        opening_balance = closing_balance = 0.0

    balance_change = closing_balance - opening_balance

    # ----- Split bank txs: settlements / fees / regular -----
    regular_bank_txs = []
    cc_settlements_total = 0.0
    bank_fee_txs = []

    for tx in bank_txs:
        if is_credit_card_settlement(tx):
            cc_settlements_total += tx.debit
        elif is_bank_fee(tx):
            bank_fee_txs.append(tx)
            regular_bank_txs.append(tx)
        else:
            regular_bank_txs.append(tx)

    # ----- Total income (all bank credits) -----
    total_income = sum(tx.credit for tx in bank_txs if tx.credit > 0)


    # ----- Total expenses -----
    bank_expenses_total = sum(tx.debit for tx in regular_bank_txs if tx.debit > 0)
    card_expenses_total = sum(tx.debit for tx in card_txs if tx.debit > 0)
    total_expenses = bank_expenses_total + card_expenses_total

    real_net = total_income - total_expenses

    # ----- Pending: ALWAYS computed against full data, not filtered -----
    settlement_billing_months = set()
    for tx in bank_txs_all:
        if is_credit_card_settlement(tx):
            bm = billing_month(tx.date)
            settlement_billing_months.add((bm.year, bm.month))

    last_settled = max(settlement_billing_months) if settlement_billing_months else None

    pending_card_txs = []
    for tx in card_txs_all:
        bm = billing_month(tx.date)
        tx_billing = (bm.year, bm.month)
        if last_settled is None or tx_billing > last_settled:
            pending_card_txs.append(tx)

    pending_fees = []
    if last_settled is not None:
        for tx in bank_txs_all:
            if is_bank_fee(tx):
                bm = billing_month(tx.date)
                if (bm.year, bm.month) > last_settled:
                    pending_fees.append(tx)

    pending_cc = sum(tx.debit for tx in pending_card_txs) + sum(tx.debit for tx in pending_fees)
    pending_list = sorted(pending_card_txs + pending_fees, key=lambda x: x.date, reverse=True)

    # ----- Past period settlements -----
    # Card txs from OUTSIDE the period whose billing month was settled WITHIN the period
    period_settlement_months = set()
    for tx in bank_txs:
        if is_credit_card_settlement(tx):
            bm = billing_month(tx.date)
            period_settlement_months.add((bm.year, bm.month))

    past_settlement_txs = []
    if period_settlement_months:
        max_settled = max(period_settlement_months)
        min_settled = min(period_settlement_months)
        period_card_ids = {id(tx) for tx in card_txs}
        for tx in card_txs_all:
            if id(tx) in period_card_ids:
                continue
            bm = billing_month(tx.date)
            tx_bm = (bm.year, bm.month)
            if min_settled <= tx_bm <= max_settled:
                past_settlement_txs.append(tx)

    past_settlements_total = sum(tx.debit - tx.credit for tx in past_settlement_txs)
    past_settlement_txs.sort(key=lambda x: x.date, reverse=True)

    # ----- Categories (bank regular + cards) -----
    all_expenses = [tx for tx in regular_bank_txs + card_txs if tx.debit > 0]

    categories_map: dict[str, list[Transaction]] = {}
    for tx in all_expenses:
        categories_map.setdefault(tx.category, []).append(tx)

    categories_summary = []
    for cat_name, txs in categories_map.items():
        categories_summary.append(CategorySummary(
            name=cat_name,
            total=sum(tx.debit for tx in txs),
            transactions=sorted(txs, key=lambda x: x.date, reverse=True)
        ))
    categories_summary.sort(key=lambda x: x.total, reverse=True)

    # ----- Monthly breakdown (only when not filtering by single month) -----
    monthly_breakdown = []
    if month is None:
        all_transactions = regular_bank_txs + card_txs
        months_map: dict[str, list[Transaction]] = {}
        for tx in all_transactions:
            bm = billing_month(tx.date)
            key = f"{bm.year}-{bm.month:02d}"
            months_map.setdefault(key, []).append(tx)

        for yyyymm in sorted(months_map.keys(), reverse=True):
            m_txs = months_map[yyyymm]
            m_label = datetime.strptime(yyyymm, "%Y-%m").strftime("%B %Y")

            m_expenses = [tx for tx in m_txs if tx.debit > 0]

            m_income = [
                tx for tx in m_txs
                if tx.credit > 0 and tx.source != "credit_card"
            ]

            m_total_income = sum(tx.credit for tx in m_income)
            m_total_expenses = sum(tx.debit for tx in m_expenses)

            m_cat_map: dict[str, list[Transaction]] = {}
            for tx in m_expenses:
                m_cat_map.setdefault(tx.category, []).append(tx)

            m_categories = []
            for c_name, c_txs in m_cat_map.items():
                m_categories.append(CategorySummary(
                    name=c_name,
                    total=sum(tx.debit for tx in c_txs),
                    transactions=sorted(c_txs, key=lambda x: x.date, reverse=True)
                ))
            m_categories.sort(key=lambda x: x.total, reverse=True)

            monthly_breakdown.append(MonthSummary(
                label=m_label,
                income=m_total_income,
                expenses=m_total_expenses,
                net=m_total_income - m_total_expenses,
                categories=m_categories
            ))

    period_label = f"{month:02d}/{year}" if year and month else (f"Year {year}" if year else "All Time")

    return ReportData(
        period_label=period_label,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        balance_change=balance_change,
        total_income=total_income,
        total_expenses=total_expenses,
        real_net=real_net,
        pending_cc=pending_cc,
        pending_transactions=pending_list,
        past_settlements=past_settlements_total,
        past_settlement_transactions=past_settlement_txs,
        categories=categories_summary,
        income_transactions=sorted(
            [tx for tx in bank_txs if tx.credit > 0],
            key=lambda x: x.date,
            reverse=True
        ),
        monthly_breakdown=monthly_breakdown
    )