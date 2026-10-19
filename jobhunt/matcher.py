"""Decide whether a job fits the user's criteria and give it a 0-100 score."""
import re

from . import config as C
from .store import LEVELS

_I = re.I


def normalize(text):
    text = (text or "").lower()
    for pat, rep in C.NORMALIZE:
        text = re.sub(pat, rep, text)
    return text


_LEVEL_WORDS = {"intern", "internship", "trainee", "senior", "sr", "junior", "jr", "lead", "principal", "entry"}
_CANON = {w: sorted(group)[0] for group in C.SYNONYMS for w in group}


def _canon(tok):
    if len(tok) > 4 and tok.endswith("s") and not tok.endswith("ss"):
        tok = tok[:-1]
    return _CANON.get(tok, tok)


def tokens(text):
    return {_canon(t) for t in re.findall(r"[a-z0-9+#]+", normalize(text)) if t not in C.STOP_WORDS}


def phrase(term):
    """Regex for a keyword as a whole word/phrase, after normalization (so C#, .NET, Node.js work)."""
    t = normalize(term).strip()
    return re.compile(r"(?<![a-z0-9])" + re.escape(t).replace(r"\ ", r"[\s-]+") + r"(?![a-z0-9])")


def min_years(text):
    """Smallest 'N years' requirement mentioned, or None."""
    text = text or ""
    nums = []
    for m in re.finditer(r"(\d{1,2})\s*(?:\+|-|–|to)?\s*(?:\d{1,2})?\s*\+?\s*(?:years?|yrs?)", text, _I):
        n = int(m.group(1))
        before = text[max(0, m.start() - 25):m.start()].lower()
        if n <= 20 and "age" not in before and "old" not in text[m.end():m.end() + 6].lower():
            nums.append(n)
    return min(nums) if nums else None


def is_night(title, desc=""):
    return bool(re.search(r"\bnight\b", title or "", _I)
                or any(re.search(p, f"{title} {desc}", _I) for p in C.NIGHT_SHIFT))


def job_type_key(text):
    t = (text or "").lower()
    if "intern" in t:
        return "internship"
    if "part" in t:
        return "part_time"
    if "contract" in t or "freelance" in t:
        return "contract"
    if "temp" in t:
        return "temporary"
    if "full" in t or "permanent" in t:
        return "full_time"
    return None


def mode_key(work_mode):
    wm = (work_mode or "").lower()
    return "remote" if wm.startswith("remote") else "hybrid" if wm.startswith("hybrid") else "onsite"


class Matcher:
    def __init__(self, criteria):
        self.c = criteria
        self.levels = set(criteria.get("levels") or LEVELS)
        self.roles = [(r, tokens(r)) for r in criteria.get("roles") or []]
        self.roles = [(r, t) for r, t in self.roles if t]
        self.role_words = {w for r, _ in self.roles for w in re.findall(r"[a-z]+", r.lower())} - _LEVEL_WORDS
        self.keywords = [(k, phrase(k)) for k in criteria.get("keywords") or [] if k.strip()]
        self.exclude = [(k, phrase(k)) for k in criteria.get("exclude") or [] if k.strip()]
        self.modes = set(criteria.get("work_modes") or ["remote", "hybrid", "onsite"])
        self.job_types = set(criteria.get("job_types") or [])
        self.min_score = int(criteria.get("min_score") or 0)
        self.max_years = max(C.LEVEL_YEARS[l][1] for l in self.levels)
        country = (criteria.get("country") or "").strip().lower()
        city = (criteria.get("city") or "").strip().lower()
        self.places = [p for p in (city, country) if p]
        regions = set(criteria.get("regions") or [])
        regions |= {name for name, countries in C.REGIONS.items() if country and country in countries}
        geo = [C.WORLDWIDE] + [re.escape(p) for p in self.places] + [re.escape(r.lower()) for r in regions]
        self.open_geo = re.compile("|".join(geo), _I)

    # ---- title-level checks (cheap, before fetching a description) ----
    def role_hits(self, title):
        tt = tokens(title)
        return [r for r, rt in self.roles if rt <= tt]

    def keyword_hits(self, text):
        n = normalize(text)
        return [k for k, p in self.keywords if p.search(n)]

    def excluded(self, title):
        n = normalize(title)
        return next((k for k, p in self.exclude if p.search(n)), None)

    def title_level(self, title):
        # Ignore words that are part of the user's own role names ("Product Manager" isn't a lead role).
        t = re.sub(r"[A-Za-z]+", lambda m: "" if m.group(0).lower() in self.role_words else m.group(0), title or "")
        for lvl in ("internship", "lead", "senior", "entry"):
            if re.search(C.LEVEL_TITLE[lvl], t, _I):
                return lvl
        if re.search(r"\s(I|1)\s*$", t):   # "Software Engineer I"
            return "entry"
        return None

    def title_ok(self, title):
        if self.excluded(title):
            return False
        lvl = self.title_level(title)
        if lvl and lvl not in self.levels:
            return False
        return bool(self.role_hits(title) or (self.keywords and self.keyword_hits(title)))

    # ---- full evaluation ----
    def _level_fit(self, job, title):
        """(ok, confident, reason)."""
        yrs = min_years(job.get("experience") or "") if job.get("experience") else \
            min_years((job.get("description") or "")[:4000])
        if yrs is not None and yrs > self.max_years + 1:
            return False, False, f"needs {yrs}+ years"
        lvl = self.title_level(title)
        if not lvl and job_type_key(job.get("job_type")) == "internship":
            lvl = "internship"
        if lvl:
            return (lvl in self.levels), True, f"{lvl} level"
        site = C.SITE_LEVELS.get((job.get("level") or "").strip().lower())
        if site:
            return bool(set(site) & self.levels), True, f"listed as {job['level']}"
        if yrs is None:
            # Can't tell. Unlabelled titles are rarely internships.
            return self.levels != {"internship"}, False, "level unknown"
        fits = any(lo - 1 <= yrs <= hi for lo, hi in (C.LEVEL_YEARS[l] for l in self.levels))
        return fits, True, f"asks for {yrs} years"

    def eligible(self, job):
        geo = job.get("geo") if job.get("geo") is not None else job.get("location") or ""
        if mode_key(job.get("work_mode")) == "remote":
            return 1 if not geo.strip() or self.open_geo.search(geo) else 0
        # On-site / hybrid: must be in your city if you gave one, otherwise anywhere in your country.
        local = self.places[:1]
        if not local:
            return 1
        return 1 if local[0] in (job.get("location") or "").lower() else 0

    def evaluate(self, job):
        """Return dict(keep, score, roles, skills, reason, night, eligible)."""
        title = job.get("title") or ""
        desc = job.get("description") or ""
        out = {"keep": False, "score": 0, "roles": [], "skills": [], "reason": "",
               "night": is_night(title, desc), "eligible": 0}

        bad = self.excluded(title)
        if bad:
            return {**out, "reason": f"excluded word: {bad}"}
        roles = self.role_hits(title)
        title_kw = self.keyword_hits(title)
        if not roles and not title_kw:
            return {**out, "reason": "title doesn't match your roles"}

        mode = mode_key(job.get("work_mode"))
        if mode not in self.modes:
            return {**out, "reason": f"{mode} not wanted"}
        jt = job_type_key(job.get("job_type"))
        if jt and jt != "internship" and self.job_types and jt not in self.job_types:
            return {**out, "reason": f"{jt} not wanted"}

        ok, confident, why = self._level_fit(job, title)
        if not ok:
            return {**out, "reason": why}

        eligible = self.eligible(job)
        if not eligible and mode != "remote":
            return {**out, "reason": "on-site outside your location"}

        skills = self.keyword_hits(f"{title} {desc}")
        score = 45 if roles else 25
        if self.keywords:
            denom = min(len(self.keywords), 8)
            score += round(30 * min(1, len(skills) / denom))
        else:
            score += 15
        score += 5 if title_kw else 0
        score += 10 if confident else 5
        score += 10 if eligible else 0
        score = min(score, 100)
        if score < self.min_score:
            return {**out, "score": score, "reason": f"weak match ({score})"}
        return {**out, "keep": True, "score": score, "roles": roles[:3], "skills": skills, "eligible": eligible}
