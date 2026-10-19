"""Run all chosen sources, filter/score against your criteria, store. `python -m jobhunt.scrape`"""
import json
import sys
from datetime import datetime, timedelta, timezone

from . import db, store
from .matcher import Matcher
from .sources import bdjobs, jobicy, linkedin, remotive

SOURCES = {"linkedin": linkedin, "remotive": remotive, "jobicy": jobicy, "bdjobs": bdjobs}


def _too_old(posted, days):
    try:
        d = datetime.fromisoformat(str(posted).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d < datetime.now(timezone.utc) - timedelta(days=days + 1)


def _store_fields(job, res):
    job.update(score=res["score"], categories=res["roles"], skills=res["skills"],
               night_shift=int(res["night"]), eligible=res["eligible"])
    return job


def run(only=None, log=print):
    criteria = store.load_criteria()
    if not criteria or not criteria.get("roles"):
        log("No search criteria yet. Finish the setup first.")
        return 0
    m = Matcher(criteria)
    con = db.connect()
    known = db.known_ids(con)
    days = int(criteria.get("posted_within") or 7)
    added = 0
    for name in criteria["sources"]:
        mod = SOURCES.get(name)
        if not mod or (only and name not in only):
            continue
        log(f"[{name}] searching...")
        try:
            jobs = mod.fetch(criteria, m, log, is_known=lambda i: i in known)
        except Exception as e:
            log(f"[{name}] failed: {e}")
            continue
        new = kept = 0
        for job in jobs:
            if job["id"] in known:
                con.execute("UPDATE jobs SET last_seen=? WHERE id=?", (db.now(), job["id"]))
                continue
            if _too_old(job.get("posted"), days):
                continue
            new += 1
            res = m.evaluate(job)
            if not res["keep"]:
                db.reject(con, job["id"], res["reason"])
                continue
            db.upsert(con, _store_fields(job, res))
            kept += 1
        con.commit()
        known = db.known_ids(con)
        added += kept
        log(f"[{name}] {new} new listings, {kept} matched")
    log(f"Done. {added} new matching jobs.")
    return added


def rescore(log=print):
    """Re-apply the current criteria to stored jobs (after you change them).
    Jobs that no longer match are removed unless you've already acted on them."""
    criteria = store.load_criteria()
    if not criteria:
        return 0
    m = Matcher(criteria)
    con = db.connect()
    dropped = 0
    for r in con.execute("SELECT * FROM jobs").fetchall():
        job = dict(r)
        job["geo"] = job["location"] if job.get("work_mode") == "Remote" else None
        res = m.evaluate(job)
        if not res["keep"] and job["status"] == "new":
            con.execute("DELETE FROM jobs WHERE id=?", (job["id"],))
            db.reject(con, job["id"], res["reason"])
            dropped += 1
        elif res["keep"]:
            con.execute("UPDATE jobs SET score=?, categories=?, skills=?, night_shift=?, eligible=? WHERE id=?",
                        (res["score"], json.dumps(res["roles"]), json.dumps(res["skills"]), int(res["night"]),
                         res["eligible"], job["id"]))
    con.commit()
    log(f"Rescored. Removed {dropped} jobs that no longer match.")
    return dropped


if __name__ == "__main__":
    args = set(sys.argv[1:])
    if args == {"rescore"}:
        rescore()
    else:
        run(only=args or None)
