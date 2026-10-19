"""LinkedIn public (guest) job search, one search per role you picked.

No login used: this hits the same endpoints the logged-out jobs page uses,
so your LinkedIn account is never exposed to automated traffic.
"""
import re
import time

from bs4 import BeautifulSoup

from .. import config as C
from . import session

SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{}"


def _get(s, url, params=None, log=print):
    for attempt in range(4):
        r = s.get(url, params=params, timeout=30)
        if r.status_code == 429:
            wait = 15 * (attempt + 1)
            log(f"  linkedin rate-limited, waiting {wait}s")
            time.sleep(wait)
            continue
        return r
    return r


def _searches(c):
    """(query, location, extra params). The guest API often ignores the workplace filter (f_WT),
    so work mode is classified afterwards from location + description."""
    levels = ",".join(sorted({x for l in c["levels"] for x in C.LINKEDIN_LEVELS[l].split(",")}))
    types = ",".join(C.LINKEDIN_JOB_TYPES[t] for t in c["job_types"] if t in C.LINKEDIN_JOB_TYPES)
    if "internship" in c["levels"]:
        types = ",".join(filter(None, [types, "I"]))
    base = {k: v for k, v in {"f_E": levels, "f_JT": types}.items() if v}
    home = ", ".join(p for p in (c.get("city"), c.get("country")) if p)
    modes = set(c["work_modes"])
    for role in c["roles"][:C.LINKEDIN_MAX_ROLES]:
        if modes & {"onsite", "hybrid"} and home:
            yield role, home, base
        if "remote" in modes:
            if c.get("country"):
                yield role, c["country"], {**base, "f_WT": "2"}
            yield f"{role} remote", "Worldwide", {**base, "f_WT": "2"}
        if not home and modes & {"onsite", "hybrid"}:
            yield role, "Worldwide", base


def classify(job, place, c):
    """Set work_mode / location / geo from LinkedIn location text + description."""
    text = f"{job['title']} {job.get('description') or ''}"
    country = (c.get("country") or "").lower()
    # A country-level location with no city is how LinkedIn lists "remote within this country".
    country_only = bool(country) and place.strip().lower() == country
    if re.search(C.HYBRID_TEXT, text, re.I):
        mode = "Hybrid"
    elif re.search(C.REMOTE_TEXT, text, re.I) or "remote" in place.lower() or country_only:
        mode = "Remote"
    else:
        mode = "On-site"
    job.update(work_mode=mode, location=place, geo=place if mode == "Remote" else None)


def fetch(c, matcher, log, is_known=lambda _id: False):
    if not c["roles"]:
        log("  linkedin: no roles chosen, skipping")
        return []
    s = session()
    found = {}
    posted = C.LINKEDIN_POSTED.get(int(c.get("posted_within") or 7), "r604800")
    for q, loc, extra in _searches(c):
        for page in range(C.LINKEDIN_PAGES):
            params = {"keywords": q, "location": loc, "f_TPR": posted, "start": page * 10, **extra}
            r = _get(s, SEARCH, params, log)
            if r.status_code != 200 or not r.text.strip():
                break
            cards = BeautifulSoup(r.text, "html.parser").select("div.base-card")
            if not cards:
                break
            for card in cards:
                nid = card.get("data-entity-urn", "").rsplit(":", 1)[-1]
                jid = f"linkedin:{nid}"
                if not nid or jid in found:
                    continue
                title = card.select_one(".base-search-card__title")
                comp = card.select_one(".base-search-card__subtitle")
                place = card.select_one(".job-search-card__location")
                when = card.select_one("time")
                found[jid] = {
                    "id": jid, "source": "LinkedIn",
                    "title": title.get_text(strip=True) if title else "",
                    "company": comp.get_text(strip=True) if comp else "",
                    "place": place.get_text(strip=True) if place else "",
                    "url": f"https://www.linkedin.com/jobs/view/{nid}/",
                    "posted": when.get("datetime") if when else None,
                    "description": "", "experience": "", "job_type": "", "salary": "",
                }
            time.sleep(2.0)
        log(f"  linkedin: '{q}' in {loc}: {len(found)} found so far")

    # Only fetch full descriptions for new jobs whose title passes the cheap filter.
    candidates = [j for j in found.values() if matcher.title_ok(j["title"])]
    todo = [j for j in candidates if not is_known(j["id"])]
    log(f"  linkedin: fetching details for {len(todo)} new candidates")
    for i, j in enumerate(todo, 1):
        r = _get(s, DETAIL.format(j["id"].split(":")[1]), log=log)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            d = soup.select_one(".show-more-less-html__markup")
            j["description"] = d.get_text(" ", strip=True) if d else ""
            for li in soup.select(".description__job-criteria-item"):
                h, v = li.select_one("h3"), li.select_one("span")
                if not h or not v:
                    continue
                h, v = h.get_text(strip=True), v.get_text(strip=True)
                if h == "Employment type":
                    j["job_type"] = v
                elif h == "Seniority level":
                    j["level"] = v
        if i % 10 == 0:
            log(f"  linkedin: {i}/{len(todo)} details")
        time.sleep(1.8)
    for j in candidates:
        classify(j, j.pop("place"), c)
    return candidates
