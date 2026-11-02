"""
categorizer.py -- the "smart" layer of Smart Civic Reporter.
Explainable NLP keyword-scoring model instead of a black-box CNN --
fast, needs no training data, and easy to unit test.
"""
import math

CATEGORY_KEYWORDS = {
    "Streetlight Fault": {
        "keywords": ["street light", "streetlight", "lamp post", "pole light", "light not working",
                     "bulb fused", "dark street", "no light"],
        "department": "Electricity Board (EB)",
    },
    "Electrical Hazard": {
        "keywords": ["wire", "cable", "spark", "short circuit", "current", "electric shock",
                      "exposed wire", "fallen wire", "transformer"],
        "department": "Electricity Board (EB)",
    },
    "Water Leakage": {
        "keywords": ["water leak", "pipe burst", "pipeline", "water pipe", "leaking water",
                     "water supply", "overflow tank"],
        "department": "Municipal Water Board",
    },
    "Drainage Block": {
        "keywords": ["drainage", "drain", "sewage", "sewer", "manhole", "gutter", "stagnant water"],
        "department": "Municipal Corporation - Sanitation",
    },
    "Pothole": {
        "keywords": ["pothole", "road damage", "broken road", "crater", "road crack"],
        "department": "Public Works Department (PWD)",
    },
    "Low-lying / Hollow Area": {
        "keywords": ["hollow", "low-lying", "lowland", "pit", "ditch", "sunken road", "waterlogging"],
        "department": "Public Works Department (PWD)",
    },
    "Sanitation Issue": {
        "keywords": ["garbage", "trash", "waste", "litter", "dirty", "uncleanliness", "dump",
                     "rubbish", "not cleaned", "filth"],
        "department": "Municipal Corporation - Sanitation",
    },
    "Mosquito Menace": {
        "keywords": ["mosquito", "mosquitoes", "dengue", "malaria", "breeding", "fogging",
                     "insect menace"],
        "department": "Public Health Department",
    },
    "Overgrown Bushes": {
        "keywords": ["overgrown", "bushes", "bush", "weeds", "unkempt", "wild grass",
                     "shrubs", "vegetation"],
        "department": "Municipal Corporation - General",
    },
    "Animal Intrusion": {
        "keywords": ["stray dog", "stray dogs", "stray cattle", "cattle roaming", "cow on road",
                     "dog bite", "animal menace", "monkey menace", "stray animal", "snake",
                     "wild animal", "bull roaming"],
        "department": "Animal Control Department",
    },
}

CRITICAL_WORDS = ["fire", "spark", "electrocute", "electrocution", "shock", "fallen wire",
                   "live wire", "child", "accident", "collapsed"]
HIGH_WORDS = ["exposed wire", "burst", "flooding", "overflow", "major", "urgent", "danger"]
MEDIUM_WORDS = ["leak", "block", "not working", "damaged"]

DUPLICATE_RADIUS_METRES = 60

DROPDOWN_CATEGORIES = [
    ("Streetlight Fault", "Street Light Fault"),
    ("Water Leakage", "Water Leakage"),
    ("Electrical Hazard", "Current Wire Cut / Lying Down"),
    ("Drainage Block", "Drainage"),
    ("Pothole", "Potholes"),
    ("Sanitation Issue", "Sanitation / Garbage"),
    ("Mosquito Menace", "Mosquito Menace"),
    ("Overgrown Bushes", "Overgrown Bushes"),
    ("Animal Intrusion", "Animal Intrusion"),
    ("Other", "Others"),
]

DEPARTMENTS = sorted({meta["department"] for meta in CATEGORY_KEYWORDS.values()} |
                      {"Municipal Corporation - General"})


def department_for_category(category: str) -> str:
    if category in CATEGORY_KEYWORDS:
        return CATEGORY_KEYWORDS[category]["department"]
    return "Municipal Corporation - General"


def classify_department(description: str):
    text = description.lower()
    best_category, best_score = "Other", 0
    for category, meta in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in meta["keywords"] if kw in text)
        if score > best_score:
            best_score, best_category = score, category
    if best_score == 0:
        return "Other", "Municipal Corporation - General"
    return best_category, CATEGORY_KEYWORDS[best_category]["department"]


def classify_priority(description: str, report_count: int = 1) -> str:
    text = description.lower()
    if any(w in text for w in CRITICAL_WORDS):
        return "Critical"
    if any(w in text for w in HIGH_WORDS) or report_count >= 5:
        return "High"
    if any(w in text for w in MEDIUM_WORDS) or report_count >= 2:
        return "Medium"
    return "Low"


def haversine_distance_metres(lat1, lon1, lat2, lon2) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def find_duplicate(new_lat, new_lon, category, existing_complaints):
    for c in existing_complaints:
        if c.category != category:
            continue
        if c.status == "Completed":
            continue
        dist = haversine_distance_metres(new_lat, new_lon, c.latitude, c.longitude)
        if dist <= DUPLICATE_RADIUS_METRES:
            return c
    return None
