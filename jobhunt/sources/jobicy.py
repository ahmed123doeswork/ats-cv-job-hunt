"""Jobicy public remote-jobs API (https://jobicy.com/api/v2/remote-jobs), searched per role."""
import re
import time

from .. import config as C
from . import session

API = "https://jobicy.com/api/v2/remote-jobs"


def fetch(c, matcher, log, is_known=lambda _id: False):
    if "remote" not in c["work_modes"]:
        log("  jobicy: remote-only site, skipped (you didn't pick remote)")
        return []
    s = session()
    seen = {}
    for role in c["roles"]:
        try:
            r = s.get(API, params={"count": C.JOBICY_COUNT, "tag": role}, timeout=30)
            r.raise_for_status()
            jobs = r.json().get("jobs") or []
        except Exception as e:
            log(f"  jobicy '{role}': {e}")
            continue
        for j in jobs:
            jid = f"jobicy:{j['id']}"
            if jid in seen:
                continue
            geo = j.get("jobGeo") or ""
            salary = ""
            if j.get("salaryMin"):
                salary = (f"{j.get('salaryCurrency', '')} {j['salaryMin']}-{j.get('salaryMax', '')} "
                          f"{j.get('salaryPeriod', '')}").strip()
            jt = j.get("jobType")
            seen[jid] = {
                "id": jid, "source": "Jobicy", "work_mode": "Remote",
                "title": (j.get("jobTitle") or "").strip(),
                "company": j.get("companyName"),
                "location": geo, "geo": geo,
                "url": j.get("url"),
                "posted": j.get("pubDate"),
                "experience": "",
                "job_type": ", ".join(jt) if isinstance(jt, list) else (jt or ""),
                "salary": salary,
                "description": re.sub(r"<[^>]+>", " ", j.get("jobDescription") or ""),
                "level": "" if j.get("jobLevel") == "Any" else j.get("jobLevel"),
            }
        time.sleep(1)
    log(f"  jobicy: {len(seen)} listings")
    return list(seen.values())
