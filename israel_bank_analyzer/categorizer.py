"""
categorizer.py - transaction categorization via keyword matching
"""

import re
from typing import Optional
from scripts.importer import Transaction


UNKNOWN_CATEGORY = "❓ Other"


MERCHANT_ALIASES = {
    "am pm": "am:pm",
    "ampm": "am:pm",
    "am pm dizengoff": "am:pm",
    "super pharm": "סופר פארם",
    "superpharm": "סופר פארם",
    "mcdonalds": "מקדונלד",
}


CATEGORIES: dict[str, list[str]] = {
    "🏦 Bank Fees & Commissions": [
        "מסלול בסיסי", "מסלול מורחב", "עמ.הקצאת אשראי", "עמלת הקצאת", "דמי ניהול", 
        "דמי כרטיס", "עמלת כרטיס", "עמל.ערוץ יש", "עמלה", "עמלות", "עמל.", "עמלת",
        "ריבית חובה", "חיובי ריבית", "חיוב ריבית", "עמלת מינימום", "עמלת חליפין", 
        "עמלת טיפול", "עמ.פקיד", "עמלת פקיד","פרעון הלוואה", "פרעון מוקדם", "פרעון חוב",
        "פרעון הלוואה מוקדם", "פרעון מוקדם חוב",
    ],

    "🏠 House & Billing": [
        # Rent & checks to landlord
        "שכירות", "דירה",
        # Municipal & building
        "ארנונה", "ועד בית", "אגודה הדדית", "ארלוזורוב אגודה",
        # Utilities
        "חשמל", "חברת חשמל", "מים", "גז",
        # Home internet & cable
        "בזק", "הוט", "013", "019",
        # Government housing
        "עמידר", "חלמיש", "דיור ציבורי", "אינטרנט ומיים"
    ],

    "🍎 Groceries": [
        "שופרסל", "רמי לוי", "מגה", "ויקטורי", "יינות ביתן", "אושר עד",
        "מחסני השוק", "קרפור", "am:pm", "טיב טעם", "קשת טעמים",
        "שוק פייסל", "החמניה", "שלי", "ירקות", "פירות",
        "ספיד","פרישוק", "סינמטק ראש פינה",
        "מקור הפיצוחים בעמ",   # ספיד בראשית - local grocery
        "דהן מרקט", "רוסמן", "סבא חביב",
        "דיווין דליקטס ויין", 'רשת כוורת בצה"ל',
        # Stored normalized (dashes become spaces before matching), so a literal
        # "מש - קר בע\"מ" still matches.
        "מש קר בע",
    ],

    "🍽️ Restaurants & Cafes": [
        "וולט", "wolt", "10bis", "מסעדה", "קפה", "פיצה", "סושי",
        "המבורגר", "פלאפל", "מקדונלד", "ארומה", "איזי פאף -קריית ים",
        "שווארמה", "שוורמה", "בורגר", "גלידה", "מאפה", "מאפייה",
        "מנדרין","מסעדת אמבר", "מסעדת טורקיז", "מסעדת בראון", "מסעדת ג'ויה",
        "גרג אודיטוריום", "גרג קניון", "גרג קרית אתא", "גרג קרית ביאליק",
        "י.ע.ל בני ציון", "י.ע.ל קרית אתא", "י.ע.ל קרית ביאליק","PAYPAL *CAFEKINNERE",
        "מסעדת אמרטי", "קונדיטוריה ליבל", "שינקין בורגר"
    ],

    "🚗 Transport": [
        # Fuel
        "דלק", "פז", "סונול", "דור אלון", "יילו", "yellow",
        # Parking & tolls
        "חניה", "מנהרות", "פנגו",
        # Car maintenance
        "פריים מוטורס", "מוסך", "טסט",
        # Vehicle licensing
        "משרד התחבורה", "מ. התחבורה",
        # Car insurance
        "ביטוח רכב", "ביטוח מנועי", "ביטוח ישיר",
        "איילון רכב", "מגדל רכב", "הפניקס רכב", "כלל רכב", "הראל רכב",
        "מנורה ביטוח חובה", "צמיגי הצומת","מ.תחבורה ר.נהיגה"
    ],
      "🚌 Public Transport": [
        # Public transport
        "אגד", "רכבת", "רב קו",
        # Ride sharing
        "גט", "יאנגו",
    ],

    "🏥 Health & Medical": [
        # Health funds
        "מכבי", "כללית", "לאומית", "מאוחדת", "קופת חולים",
        # Hospitals & clinics
        "אסותא", "הדסה", "איכילוב", "שיבא", "מרפאה",
        # Pharmacies
        "סופר פארם", "גוד פארם", "בית מרקחת",
        # Health insurance
        "ביטוח בריאות", "ביטוח סיעודי", "ביטוח חיים",
        "איילון בריאות", "מגדל בריאות", "הפניקס בריאות",
        "כלל בריאות", "הראל בריאות",
        "ביטוח כללי מנורה",
        # Dental & optical
        "שיניים", "דנטל", "אופטיקה",
        "TOP PHARM", "טופ פארם", 'קורקט יבוא ושיווק מתנות בע"מ',
        "IHERB",
        # Doctors / clinics
        'ד"ר גב', "דר גב", "דר דימיטרי", "חיימוביץ", "מרפאת", "פיזיותרפיה",
    ],

    "💳 Subscriptions & Monthly Bills": [
        # Streaming
        "netflix", "spotify", "apple tv", "disney", "youtube",
        # Phone carriers
        "סלקום", "פרטנר", "פלאפון", "גולן טלקום",
        "מרכז לבריאות השיער", "APPLE.COM BILL", "apple.com",
        # Cloud / AI / digital services
        "anthropic", "claude", "google one", "openai", "chatgpt", "microsoft",
        "icloud", "dropbox", "google storage",
        # Debit card aggregated charges (normalized: dash → space)
        "דירקט מצטבר", "דירקט", "HOT"
    ],

    "🛍️ Shopping & Clothing": [
        "zara", "h&m", "קסטרו", "פוקס", "רנואר", "גולף",
        "amazon", "istore", "ksp", "ivory",
        "ikea", "ace", "we shose", "נעליים", "ביגוד",
        "הום סנטר",
        "ביג מקס", "מקס סטוק",
        "Temu.com", "זול סטוק קרית מוצקין", "הלב הכחול", "סבא חביב - סניף קרית אתא", "ksp",
        "קיי.אס.פי",
        # Online marketplaces
        "איקאה", "wildberries", "aliexpress", "fruugo", "temu", "shein", "asos",
        # Musical instruments store
        "כלי זמר",
    ],

    "🏋️ Sport & Fitness": [
        "gym", "מכון כושר", "הולמס פלייס", "בריכה", "יוגה", "פילאטיס", "כושר קריית אתא",
        "דקאתלון", "decathlon",
        "ספורט", "מרכז הספורט", "ספייס קרית אתא", "ספייס קרית",
    ],

    "🎬 Entertainment": [
        "קולנוע", "תיאטרון", "כרטיסים","אתדגיס אור ד.ג. בע''מ",
        "סינמה סיטי", "יס פלאנט","סינמטק", "בארד פרודקשנס-יציל",
        "חניון קניון סינמול","איזי פאף",
        # Gaming
        "steam", "fortnite", "epic games", "playstation", "xbox", "nintendo",
        "roblox", "google play",
    ],
    

    "✈️ Travel": [
        "booking", "airbnb", "ryanair", "wizz", "easyjet", "אל על",
        "מלון", "טיסה","ישראייר","TUI CRUISES", "רשות הטבע והגנים",
    ],

    "💎 Savings & Pension": [
        "מיטב דש", "גמל ופ", "פנסיה", "קרן השתלמות", "תגמולים",
    ],

    "💰 Income": [
        "משכורת", "שכר", "זיכוי", "החזר",
        'מט"ב', "מטב", "ביטוח לאומי זיכוי",
        "ירין כח אדם", "משרד הבינוי", 'מופ"ת',
        "זכוי מת. חסכון",
    ],

    "🎓 Education": [
        # Courses & exam prep (e.g. psychometric course provider "או.קיי")
        "פסיכומטרי", "קורס", "לימודים", "שכר לימוד",
        "אוניברסיטה", "מכללה", "או.קיי", "אוקיי",
    ],

    # Generic money transfers — kept LAST so a meaningful word inside a transfer
    # note ("...דירה", "...שוורמה") is categorized by that word first, and only a
    # bare transfer with no other signal falls through to here.
    "💸 Transactions": [
        "העברה", "העברת", "העב'",
        "bit העברת", "bit",
        "ז.בנק", "ז. בנק",
        "הע. אינטרנטית", "העברה אינטרנטית", "משיכה מבנקט",
    ],
}


def normalize_description(text: str) -> str:
    """Lowercase, strip locations, digits, and punctuation noise."""
    text = text.lower()

    locations = [
        "tel aviv", "tlv", "jerusalem", "haifa", "beer sheva",
        "תל אביב", "חיפה", "ירושלים",
    ]
    for loc in locations:
        text = text.replace(loc, "")

    text = re.sub(r"\d+", "", text)
    text = text.replace("-", " ").replace("/", " ").replace(":", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def canonicalize(text: str) -> str:
    """Apply merchant aliases on top of normalization."""
    text = normalize_description(text)

    for alias, canonical in MERCHANT_ALIASES.items():
        if alias in text:
            return canonical

    return text


def _match_keywords(description: str) -> Optional[str]:
    """Find the first category whose keyword appears in description."""
    desc = canonicalize(description)

    for category, keywords in CATEGORIES.items():
        for kw in keywords:
            kw_lower = kw.lower()
            # Short keywords (3 chars or less) require word boundary match
            if len(kw_lower) <= 3:
                if re.search(rf"(^|\s){re.escape(kw_lower)}(\s|$)", desc):
                    return category
            else:
                if kw_lower in desc:
                    return category

    return None


# Rent labels — language-based, amount-independent so it works for any user.
# A "שכירות"-labelled payment is also caught via the House & Billing keywords;
# these variants cover abbreviations landlords/tenants commonly write.
RENT_KEYWORDS = ["שכירות", 'שכ"ד', "שכ''ד", "דמי שכירות", "rent"]


HOUSE_CATEGORY = "🏠 House & Billing"
TRANSACTIONS_CATEGORY = "💸 Transactions"


def _is_rent(tx: Transaction) -> bool:
    """Rent → House & Billing, regardless of amount.

    Two universal signals (no hardcoded sum):
    - a paper check (``שיק``): in Israel checks are written mostly to landlords;
    - any payment whose text carries a rent label (``שכירות`` / ``שכ"ד`` ...).
    """
    desc = tx.description.strip()
    if desc == "שיק" or desc.startswith("שיק "):
        return True
    return any(kw in desc for kw in RENT_KEYWORDS)


def _recurring_rent_amounts(transactions: list[Transaction]) -> set[int]:
    """Learn each user's rent amount(s) from the data, no hardcoded sum.

    An amount is treated as rent only when it shows up at least twice as solid
    rent evidence (a check or a ``שכירות``-labelled debit). The repetition gate
    keeps a one-off check or coincidental payment from hijacking unrelated
    transfers. The learned amounts let us also catch the months where the same
    rent was paid by a bare transfer (no check, no label).
    """
    counts: dict[int, int] = {}
    for tx in transactions:
        if tx.debit > 0 and _is_rent(tx):
            key = round(tx.debit)
            counts[key] = counts.get(key, 0) + 1
    return {amt for amt, n in counts.items() if n >= 2}


def categorize(transactions: list[Transaction]) -> list[Transaction]:
    """Assign a category to every transaction."""
    rent_amounts = _recurring_rent_amounts(transactions)

    for tx in transactions:
        # Special rule: rent (checks + rent-labelled payments) → House & Billing
        if _is_rent(tx):
            tx.category = HOUSE_CATEGORY
            continue

        # A bare digital transfer with no other info → generic Transactions
        if tx.description.strip() == "העברה דיגיטל":
            base = TRANSACTIONS_CATEGORY
        else:
            base = _match_keywords(tx.description) or UNKNOWN_CATEGORY

        # Auto-detected rent: a generic transfer whose amount matches a
        # recurring rent amount learned above is almost certainly that month's
        # rent paid without a check/label. Only override generic transfers
        # (Transactions), never a real categorized purchase.
        if (
            base == TRANSACTIONS_CATEGORY
            and tx.debit > 0
            and round(tx.debit) in rent_amounts
        ):
            tx.category = HOUSE_CATEGORY
        else:
            tx.category = base

    return transactions