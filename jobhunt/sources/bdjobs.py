"""BDjobs (Bangladesh) via its public search API, searched per role.

Only used when your country is Bangladesh. Full descriptions come from the job page,
which embeds the job as JSON (ng-state).
"""
import html
import json
import re
import time

from .. import config as C
from . import session

API = "https://api.bdjobs.com/Jobs/api/JobSearch/GetJobSearch"
DETAIL = "https://bdjobs.com/h/details/{}"
WORKPLACE_HOME = "1"


def _strip(text):
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _searches(c):
    modes = set(c["work_modes"])
    local = {"location": C.BDJOBS_DHAKA} if "dhaka" in (c.get("city") or "").lower() else {}
    for role in c["roles"]:
        if "remote" in modes:
            yield role, {"workplace": WORKPLACE_HOME}
        if modes & {"onsite", "hybrid"}:
            yield role, local


def _work_mode(workplace, remote_search):
    wp = (workplace or "").lower()
    if "home" in wp and "office" in wp:
        return "Hybrid"
    if "home" in wp or remote_search:
        return "Remote"
    return "On-site"


def _detail(s, jid):
    r = s.get(DETAIL.format(jid), timeout=30)
    r.raise_for_status()
    m = re.search(r'<script id="ng-state" type="application/json">(.*?)</script>', r.text, re.S)
    if not m:
        return None
    stack = [json.loads(m.group(1))]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            if "JobLocation" in o and "JobDescription" in o:
                return o
            stack.extend(o.values())
        elif isinstance(o, list):
            stack.extend(o)
    return None


def fetch(c, matcher, log, is_known=lambda _id: False):
    if (c.get("country") or "").strip().lower() != "bangladesh":
        log("  bdjobs: Bangladesh-only site, skipped")
        return []
    s = session()
    s.headers.update({"Origin": "https://bdjobs.com", "Referer": "https://bdjobs.com/"})
    seen = {}
    for kw, extra in _searches(c):
        remote_search = "workplace" in extra
        for page in range(1, C.BDJOBS_MAX_PAGES + 1):
            params = {"keyword": kw, "pg": page, "rpp": 50, "isPro": 0,
                      "ToggleJobs": "true", "isFresher": "false", **extra}
            try:
                r = s.get(API, params=params, timeout=30)
                r.raise_for_status()
                d = r.json()
            except Exception as e:
                log(f"  bdjobs '{kw}' p{page}: {e}")
                break
            for j in (d.get("data") or []) + (d.get("premiumData") or []):
                jid = f"bdjobs:{j['Jobid']}"
                if jid in seen:
                    continue
                mode = _work_mode(j.get("WorkPlace"), remote_search)
                place = f"{j.get('location', '')}, Bangladesh".strip(", ")
                seen[jid] = {
                    "id": jid, "source": "BDjobs", "work_mode": mode,
                    "title": (j.get("jobTitle") or "").strip(),
                    "company": j.get("companyName"),
                    "location": place, "geo": "Bangladesh",
                    "url": f"https://jobs.bdjobs.com/jobdetails/?id={j['Jobid']}",
                    "posted": j.get("publishDate"),
                    "deadline": j.get("deadlineDB"),
                    "experience": j.get("experience") if j.get("experience") not in ("NA", "") else "",
                    "job_type": j.get("JobType"),
                    "salary": "" if j.get("Salary") in ("--", None) else j.get("Salary"),
                    "description": _strip(j.get("jobDescription")),
                }
            if page >= ((d.get("common") or {}).get("totalpages") or 1):
                break
            time.sleep(0.4)
        time.sleep(0.4)
    log(f"  bdjobs: {len(seen)} listings")

    todo = [j for j in seen.values() if not is_known(j["id"]) and matcher.title_ok(j["title"])]
    log(f"  bdjobs: fetching details for {len(todo)} new candidates")
    for i, j in enumerate(todo, 1):
        try:
            d = _detail(s, j["id"].split(":")[1])
        except Exception as e:
            log(f"  bdjobs detail {j['id']}: {e}")
            d = None
        if d:
            j["description"] = " ".join(_strip(d.get(k)) for k in (
                "JobDescription", "AdditionJobRequirements", "SuggestedSkills", "SkillsRequired",
                "EducationRequirements", "JobOtherBenifits"))
            exp = _strip(d.get("experience"))
            if exp:
                j["experience"] = exp[:200]
            if d.get("JobSalaryRangeText") not in (None, "", "--"):
                j["salary"] = d["JobSalaryRangeText"]
        if i % 25 == 0:
            log(f"  bdjobs: {i}/{len(todo)} details")
        time.sleep(0.4)
    return list(seen.values())
