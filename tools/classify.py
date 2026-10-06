"""Classify events into the 8 categories used by the gallery.

Order matters. "internal" is tested first because staff events are worded
exactly like public ones -- "Physician Shareholder's End-of-Summer
Celebration" would otherwise land in "cultural". Categories are exclusive;
partners are a separate, cross-cutting field.
"""
import re

CATEGORIES = ("internal", "opening", "gala", "sponsorship", "seminar",
              "fair", "cultural", "other")

LABELS = {
    "internal": "Internal / Provider",
    "opening": "Grand Openings",
    "gala": "Galas & Awards",
    "sponsorship": "Sponsorships & Walks",
    "seminar": "Health Seminars",
    "fair": "Community Health Fairs",
    "cultural": "Cultural & Parades",
    "other": "Other",
}

PUBLISHABLE_CATEGORIES = tuple(c for c in CATEGORIES if c != "internal")

# Keyword sets, tested in CATEGORIES order.
_RULES = {
    "internal": ("team building", "rendr dinner", "holiday party", "provider dinner",
                 "shareholder", "physician celebration", "end-of-summer",
                 "end of summer", "end_of _year", "end of year physician",
                 "staff ", "employee"),
    "opening": ("grand opening", "open house", "ribbon cutting", "supersite open"),
    "gala": ("gala", "anniversary", "award", "ceremony", "banquet"),
    "sponsorship": ("walk", "swim across", "golf", "marathon", "run for", "title sponsor"),
    "seminar": ("seminar", "health talk", "healthtalk", "health education", "lecture",
                "prevention", "nutrition"),
    "fair": ("health fair", "wellness", "expo", "resource fair", "resources fair",
             "awareness fair", "community event", "flu shot", "screening", "health day",
             "community day", "wellness day", "family day", "spring into health",
             "wechat"),
    "cultural": ("lunar new year", "lny", "parade", "heritage", "mother", "father",
                 "birthday", "celebration", "cultural", "easter", "picnic", "festival",
                 "senior center", "senior event", "appreciation", "eggstravaganza"),
}

# Canonical partner name -> aliases matched as whole words.
PARTNERS = {
    "UnitedHealthcare": ("uhc", "unitedhealthcare", "united healthcare"),
    "VNS Health": ("vns", "vns health"),
    "HCS": ("hcs",),
    "Fidelis Care": ("fidelis",),
    "WellCare": ("wellcare",),
    "Healthfirst": ("healthfirst",),
    "Centerlight": ("centerlight",),
    "Anthem BCBS": ("anthem", "bcbs"),
    "VillageCareMax": ("villagecaremax", "villagecare"),
    "CPC": ("cpc", "nan shan"),
    "CCBA": ("ccba",),
    "ACAP": ("acap",),
    "UCA": ("uca", "ucaob"),
    "LiveOnNY": ("liveonny",),
    "CCPH": ("ccph",),
}

# Two name words only. Three would swallow the trailing topic word in
# "Dr. Xian Cheung ACAP Seminar" and "Dr. Harry He Liver Disease".
_PHYSICIAN_DR = re.compile(r"\bDr\.?\s+([A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)?)")
_PHYSICIAN_MD = re.compile(r"\b([A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,3}),\s*MD\b")


def category(title):
    low = title.lower()
    for cid in CATEGORIES:
        if cid == "other":
            continue
        for keyword in _RULES[cid]:
            if keyword in low:
                return cid
    return "other"


def partners(title):
    low = title.lower()
    found = set()
    for canonical, aliases in PARTNERS.items():
        for alias in aliases:
            if re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(alias), low):
                found.add(canonical)
                break
    return sorted(found)


def physician(title):
    match = _PHYSICIAN_DR.search(title)
    if match:
        # "Dr. Brian Poon's Prevention..." captures "Brian Poon's".
        words = [re.sub(r"'s$", "", w) for w in match.group(1).split()]
        if words:
            return "Dr. " + " ".join(words[:2])
    match = _PHYSICIAN_MD.search(title)
    if match:
        return "%s, MD" % match.group(1)
    return None
