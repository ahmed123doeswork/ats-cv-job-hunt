"""Remotive public remote-jobs API (https://remotive.com/api/remote-jobs), searched per role."""
import html
import re
import time

from .. import config as C
from . import session

API = "https://remotive.com/api/remote-jobs"


def _text(h):
    h = re.sub(r"<\s*(br|/p|/li|/h\d)\s*/?>", "\n", h or "", flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", " ", h)).strip()


def fetch(c, matcher, log, is_known=lambda _id: False):
    if "remote" not in c["work_modes"]:
        log("  remotive: remote-only site, skipped (you didn't pick remote)")
        return []
    s = session()
    seen = {}
    for role in c["roles"]:
        try:
            r = s.get(API, params={"search": role, "limit": C.REMOTIVE_LIMIT}, timeout=30)
            r.raise_for_status()
            jobs = r.json().get("jobs") or []
        except Exception as e:
            log(f"  remotive '{role}': {e}")
            continue
        for j in jobs:
            jid = f"remotive:{j['id']}"
            if jid in seen:
                continue
            geo = j.get("candidate_required_location") or ""
            seen[jid] = {
                "id": jid, "source": "Remotive", "work_mode": "Remote",
                "title": (j.get("title") or "").strip(),
                "company": j.get("company_name"),
                "location": geo, "geo": geo,
                "url": j.get("url"),
                "posted": j.get("publication_date"),
                "experience": "",
                "job_type": (j.get("job_type") or "").replace("_", " "),
                "salary": j.get("salary") or "",
                "description": _text(j.get("description")),
            }
        time.sleep(1)
    log(f"  remotive: {len(seen)} listings")
    return list(seen.values())
