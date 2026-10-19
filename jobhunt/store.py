"""The user's CV (profile.json) and job-search criteria (criteria.json), stored in data/."""
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
PROFILE_PATH = DATA / "profile.json"
CRITERIA_PATH = DATA / "criteria.json"

LEVELS = ["internship", "entry", "mid", "senior", "lead"]
WORK_MODES = ["remote", "hybrid", "onsite"]
JOB_TYPES = ["full_time", "part_time", "contract", "temporary"]
SOURCES = ["linkedin", "remotive", "jobicy", "bdjobs"]

DEFAULT_PROFILE = {
    "personal": {"name": "", "headline": "", "email": "", "phone": "", "location": "",
                 "linkedin": "", "website": ""},
    "summary": "",
    "experience": [],      # {title, company, location, start, end, current, bullets: [str]}
    "education": [],       # {degree, school, location, start, end, details}
    "skills": [],          # {group, items: [str]}
    "projects": [],        # {name, role, link, start, end, bullets: [str]}
    "certifications": [],  # {name, issuer, date}
    "languages": [],       # {name, level}
    "awards": [],          # {name, detail}
}

DEFAULT_CRITERIA = {
    "levels": ["entry", "mid"],
    "roles": [],
    "keywords": [],
    "exclude": [],
    "country": "",
    "city": "",
    "regions": [],          # remote jobs restricted to these regions also count as open to you
    "work_modes": ["remote", "hybrid", "onsite"],
    "job_types": ["full_time", "contract"],
    "posted_within": 7,     # days: 1 | 7 | 30
    "sources": ["linkedin", "remotive", "jobicy"],
    "min_score": 35,
}


def _read(path, default):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {**json.loads(json.dumps(default)), **data}


def _write(path, data):
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load_profile():
    return _read(PROFILE_PATH, DEFAULT_PROFILE)


def save_profile(data):
    clean = {k: data.get(k, v) for k, v in DEFAULT_PROFILE.items()}
    clean["complete"] = bool(data.get("complete"))
    _write(PROFILE_PATH, clean)
    return clean


def load_criteria():
    return _read(CRITERIA_PATH, DEFAULT_CRITERIA)


def save_criteria(data):
    clean = {k: data.get(k, v) for k, v in DEFAULT_CRITERIA.items()}
    clean["levels"] = [x for x in clean["levels"] if x in LEVELS]
    clean["work_modes"] = [x for x in clean["work_modes"] if x in WORK_MODES]
    clean["job_types"] = [x for x in clean["job_types"] if x in JOB_TYPES]
    clean["sources"] = [x for x in clean["sources"] if x in SOURCES]
    for k in ("roles", "keywords", "exclude", "regions"):
        seen, out = set(), []
        for v in clean[k]:
            v = str(v).strip()
            if v and v.lower() not in seen:
                seen.add(v.lower())
                out.append(v)
        clean[k] = out
    clean["posted_within"] = int(clean["posted_within"]) if str(clean["posted_within"]).isdigit() else 7
    clean["min_score"] = max(0, min(90, int(clean.get("min_score") or 0)))
    clean["complete"] = bool(data.get("complete"))
    _write(CRITERIA_PATH, clean)
    return clean


def criteria_fingerprint(criteria):
    """Changes whenever matching-relevant criteria change, so earlier rejections get re-checked."""
    keys = ("levels", "roles", "keywords", "exclude", "country", "city", "regions", "work_modes",
            "job_types", "min_score")
    blob = json.dumps({k: criteria.get(k) for k in keys}, sort_keys=True).lower()
    return hashlib.sha1(blob.encode()).hexdigest()[:12]
