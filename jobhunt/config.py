"""Source settings and matching vocabularies.

What to search for (roles, level, keywords, location) is chosen in the setup screens and saved to
data/criteria.json. This file only holds the technical knobs that apply to every user.
"""

# ---- Sources -----------------------------------------------------------------
LINKEDIN_PAGES = 2            # 10 results per page, per search
LINKEDIN_MAX_ROLES = 10       # searches are per role; cap to keep a run under ~15 minutes
LINKEDIN_POSTED = {1: "r86400", 7: "r604800", 30: "r2592000"}
# LinkedIn experience-level filter codes: 1 internship, 2 entry, 3 associate, 4 mid-senior, 5 director, 6 executive
LINKEDIN_LEVELS = {"internship": "1", "entry": "2", "mid": "3,4", "senior": "4", "lead": "4,5"}
LINKEDIN_JOB_TYPES = {"full_time": "F", "part_time": "P", "contract": "C", "temporary": "T"}

BDJOBS_MAX_PAGES = 4          # 50 results per page
BDJOBS_DHAKA = "14"           # BDjobs location id for Dhaka district

REMOTIVE_LIMIT = 60           # per role
JOBICY_COUNT = 50             # per role

# ---- Seniority ---------------------------------------------------------------
# Words in a title that pin down its level. Checked from most to least senior.
LEVEL_TITLE = {
    "internship": r"\bintern(ship)?s?\b|\btrainee\b|\bapprentice(ship)?\b|\bstudent\b|\bco-?op\b|\bwerkstudent",
    "lead": r"\blead\b|\bprincipal\b|\bstaff\b|\bhead of\b|\bhead\b|\bdirector\b|\barchitect\b|\bmanager\b|\bvp\b|"
            r"\bvice president\b|\bchief\b|\bc[tef]o\b",
    "senior": r"\bsenior\b|\bsr\.?\b|\bexpert\b|\bIII\b|\blevel 3\b",
    "entry": r"\bjunior\b|\bjr\.?\b|\bentry[\s-]?level\b|\bgraduate\b|\bfresher\b|\bnew grad\b|\bearly career\b|"
             r"\bassociate\b|\blevel 1\b",
}
# Years of experience each level usually asks for (min, max) — used when the title doesn't say.
LEVEL_YEARS = {"internship": (0, 1), "entry": (0, 2), "mid": (2, 5), "senior": (5, 10), "lead": (7, 30)}
# How each site labels seniority -> our levels.
SITE_LEVELS = {
    "internship": ["internship"], "entry level": ["entry"], "associate": ["entry", "mid"],
    "mid-senior level": ["mid", "senior"], "director": ["lead"], "executive": ["lead"],
    "junior": ["entry"], "midweight": ["mid"], "senior": ["senior"], "lead": ["lead"],
}

# ---- Title matching ----------------------------------------------------------
# Spelling variants folded together before roles are compared with job titles.
NORMALIZE = [
    (r"front[\s-]+end", "frontend"), (r"back[\s-]+end", "backend"), (r"full[\s-]+stack", "fullstack"),
    (r"dev[\s-]?ops", "devops"), (r"\bui\s*/\s*ux\b", "ui ux"), (r"\bux\s*/\s*ui\b", "ui ux"),
    (r"\bsr\.?\s", "senior "), (r"\bjr\.?\s", "junior "), (r"\bqa\b", "qa"), (r"\.net\b", " dotnet"),
    (r"\bc#", "csharp"), (r"\bnode\.?js\b", "nodejs"), (r"\breact\.?js\b", "react"), (r"\bvue\.?js\b", "vue"),
    (r"&", " and "),
]
# Words that mean the same thing in a job title.
SYNONYMS = [
    {"developer", "engineer", "programmer", "dev"},
    {"qa", "tester", "test", "quality", "sqa"},
    {"designer", "design"},
    {"analyst", "analytics"},
    {"manager", "management", "mgr"},
    {"marketing", "marketer"},
    {"representative", "rep", "executive", "associate", "specialist"},
    {"accountant", "accounting", "accounts"},
    {"hr", "human", "people"},
    {"recruiter", "recruiting", "recruitment", "talent"},
    {"administrator", "admin"},
    {"writer", "copywriter", "content"},
    {"support", "service", "success"},
]
STOP_WORDS = {"a", "an", "the", "of", "and", "or", "for", "in", "to", "with", "at", "on", "senior", "junior",
              "lead", "mid", "level", "entry", "intern", "internship", "remote", "i", "ii", "iii"}

# ---- Location ----------------------------------------------------------------
# Remote jobs that say these are open to anyone.
WORLDWIDE = r"anywhere|worldwide|global|international|any location|all countries|remote$|^remote\b(?!.*\bonly\b)"
# Region names a remote listing might use, with the countries they cover.
REGIONS = {
    "Asia": ["bangladesh", "india", "pakistan", "sri lanka", "nepal", "china", "japan", "korea", "singapore",
             "malaysia", "indonesia", "philippines", "vietnam", "thailand", "hong kong", "taiwan"],
    "APAC": ["bangladesh", "india", "pakistan", "sri lanka", "nepal", "china", "japan", "korea", "singapore",
             "malaysia", "indonesia", "philippines", "vietnam", "thailand", "australia", "new zealand"],
    "EMEA": ["united kingdom", "uk", "ireland", "germany", "france", "spain", "italy", "netherlands", "poland",
             "portugal", "sweden", "norway", "denmark", "finland", "egypt", "nigeria", "kenya", "south africa",
             "uae", "united arab emirates", "saudi arabia", "israel", "turkey", "morocco"],
    "Europe": ["united kingdom", "uk", "ireland", "germany", "france", "spain", "italy", "netherlands", "poland",
               "portugal", "sweden", "norway", "denmark", "finland", "austria", "belgium", "switzerland",
               "czech", "romania", "greece", "hungary", "ukraine"],
    "Middle East": ["uae", "united arab emirates", "saudi arabia", "qatar", "kuwait", "bahrain", "oman", "jordan",
                    "lebanon", "israel", "turkey", "egypt"],
    "Africa": ["nigeria", "kenya", "south africa", "egypt", "ghana", "morocco", "ethiopia", "uganda", "tanzania"],
    "LATAM": ["mexico", "brazil", "argentina", "colombia", "chile", "peru", "uruguay", "costa rica", "ecuador"],
    "North America": ["united states", "usa", "us", "canada", "mexico"],
}

# ---- Tags --------------------------------------------------------------------
NIGHT_SHIFT = [
    r"night[\s-]?shift", r"\bus[\s-]?(shift|hours|time[\s-]?zone)", r"overnight", r"graveyard",
    r"\d{1,2}(:\d{2})?\s*(pm|p\.m\.)\s*(-|–|to)\s*\d{1,2}(:\d{2})?\s*(am|a\.m\.)",
]
REMOTE_TEXT = r"\bremote\b|work from home|work-from-home|\bwfh\b|fully distributed"
HYBRID_TEXT = r"\bhybrid\b"
