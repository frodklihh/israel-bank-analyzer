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
        "שכירות",
        # Municipal & building
        "ארנונה", "ועד בית", "אגודה הדדית", "ארלוזורוב אגודה",
        # Utilities
        "חשמל", "חברת חשמל", "מים", "גז",
        # Home internet & cable
        "בזק", "הוט", "013", "019",
        # Government housing
        "עמידר", "חלמיש", "דיור ציבורי", "אינטרנט ומיים"
    ],

    "💸 Transactions": [
        "העברה", "העברת", "העב'",
        "bit העברת",
        "ז.בנק", "ז. בנק",
        "הע. אינטרנטית", "העברה אינטרנטית",
    ],

    "🍎 Groceries": [
        "שופרסל", "רמי לוי", "מגה", "ויקטורי", "יינות ביתן", "אושר עד",
        "מחסני השוק", "קרפור", "am:pm", "טיב טעם", "קשת טעמים",
        "שוק פייסל", "החמניה", "שלי", "ירקות", "פירות",
        "ספיד","פרישוק", "סינמטק ראש פינה",
        "מקור הפיצוחים בעמ",   # ספיד בראשית - local grocery
        "דהן מרקט", "רוסמן", "סבא חביב",
        "דיווין דליקטס ויין", 'רשת כוורת בצה"ל'
    ],

    "🍽️ Restaurants & Cafes": [
        "וולט", "wolt", "10bis", "מסעדה", "קפה", "פיצה", "סושי",
        "המבורגר", "פלאפל", "מקדונלד", "ארומה", "איזי פאף -קריית ים",
        "שווארמה", "גלידה", "מאפה", "מאפייה", 
        "מנדרין","מסעדת אמבר", "מסעדת טורקיז", "מסעדת בראון", "מסעדת ג'ויה",
        "גרג אודיטוריום", "גרג קניון", "גרג קרית אתא", "גרג קרית ביאליק",
        "י.ע.ל בני ציון", "י.ע.ל קרית אתא", "י.ע.ל קרית ביאליק","PAYPAL *CAFEKINNERE",
        "מסעדת אמרטי", "קונדיטוריה ליבל"
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
        "מנורה ביטוח חובה", "צמיגי הצומת",
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
    ],

    "💳 Subscriptions & Monthly Bills": [
        # Streaming
        "netflix", "spotify", "apple tv", "disney", "youtube",
        # Phone carriers
        "סלקום", "פרטנר", "פלאפון", "גולן טלקום",
        "מרכז לבריאות השיער", "APPLE.COM BILL",
        # Debit card aggregated charges (normalized: dash → space)
        "דירקט מצטבר", "דירקט",
    ],

    "🛍️ Shopping & Clothing": [
        "zara", "h&m", "קסטרו", "פוקס", "רנואר", "גולף",
        "amazon", "istore", "ksp", "ivory",
        "ikea", "ace", "we shose", "נעליים", "ביגוד",
        "הום סנטר",
        "ביג מקס", "מקס סטוק",
        "Temu.com", "זול סטוק קרית מוצקין", "הלב הכחול", "סבא חביב - סניף קרית אתא", "ksp",
        "קיי.אס.פי",
    ],

    "🏋️ Sport & Fitness": [
        "gym", "מכון כושר", "הולמס פלייס", "בריכה", "יוגה", "פילאטיס", "כושר קריית אתא",
        "דקאתלון", "decathlon",
    ],

    "🎬 Entertainment": [
        "קולנוע", "תיאטרון", "כרטיסים","אתדגיס אור ד.ג. בע''מ",
        "סינמה סיטי", "יס פלאנט","סינמטק", "בארד פרודקשנס-יציל", 
        "חניון קניון סינמול","איזי פאף",
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


RENT_AMOUNT = 4500.0
RENT_TOLERANCE = 50.0  # ±50₪ counts as rent


def _is_rent_check(tx: Transaction) -> bool:
    """A check or digital transfer of ~4500₪ is treated as rent."""
    desc = tx.description.strip()
    if desc not in ("שיק", "העברה דיגיטל"):
        return False
    return abs(tx.debit - RENT_AMOUNT) <= RENT_TOLERANCE

def categorize(transactions: list[Transaction]) -> list[Transaction]:
    """Assign a category to every transaction."""
    for tx in transactions:
        # Special rule: rent goes to House & Billing
        if _is_rent_check(tx):
            tx.category = "🏠 House & Billing"
            continue

        # Special rule: other checks and transfers go to Transactions
        if tx.description.strip() in ("שיק", "העברה דיגיטל"):
            tx.category = "💸 Transactions"
            continue  # <-- 
        category = _match_keywords(tx.description)
        tx.category = category if category else UNKNOWN_CATEGORY

    return transactions