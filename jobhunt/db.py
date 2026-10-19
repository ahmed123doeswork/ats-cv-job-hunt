import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jobs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,      -- source:native_id
    source      TEXT NOT NULL,
    title       TEXT NOT NULL,
    company     TEXT,
    location    TEXT,
    url         TEXT NOT NULL,
    posted      TEXT,
    deadline    TEXT,
    experience  TEXT,
    job_type    TEXT,
    salary      TEXT,
    description TEXT,
    eligible    INTEGER DEFAULT 0,
    score       INTEGER DEFAULT 0,
    categories  TEXT DEFAULT '[]',
    resume      TEXT,
    status      TEXT DEFAULT 'new',    -- new | saved | applied | interview | rejected | hidden
    notes       TEXT DEFAULT '',
    first_seen  TEXT,
    last_seen   TEXT
);
CREATE TABLE IF NOT EXISTS seen_rejected (id TEXT PRIMARY KEY, reason TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""
MIGRATIONS = {
    "work_mode": "ALTER TABLE jobs ADD COLUMN work_mode TEXT DEFAULT 'Remote'",
    "night_shift": "ALTER TABLE jobs ADD COLUMN night_shift INTEGER DEFAULT 0",
    "skills": "ALTER TABLE jobs ADD COLUMN skills TEXT DEFAULT '[]'",
}


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(jobs)")}
    for col, sql in MIGRATIONS.items():
        if col not in cols:
            con.execute(sql)
    con.commit()
    sync_criteria(con)
    return con


def sync_criteria(con):
    """Criteria changed -> forget earlier rejections so those listings get re-checked."""
    from . import store
    criteria = store.load_criteria()
    if not criteria:
        return
    fp = store.criteria_fingerprint(criteria)
    row = con.execute("SELECT value FROM meta WHERE key='criteria'").fetchone()
    if not row or row[0] != fp:
        con.execute("DELETE FROM seen_rejected")
        con.execute("INSERT OR REPLACE INTO meta VALUES ('criteria', ?)", (fp,))
        con.commit()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def known_ids(con):
    ids = {r[0] for r in con.execute("SELECT id FROM jobs")}
    ids |= {r[0] for r in con.execute("SELECT id FROM seen_rejected")}
    return ids


def upsert(con, job):
    """Insert a new job or refresh scrape fields; never touches status/notes."""
    t = now()
    con.execute(
        """INSERT INTO jobs (id, source, title, company, location, url, posted, deadline, experience,
                             job_type, salary, description, eligible, score, categories, skills,
                             work_mode, night_shift, first_seen, last_seen)
           VALUES (:id, :source, :title, :company, :location, :url, :posted, :deadline, :experience,
                   :job_type, :salary, :description, :eligible, :score, :categories, :skills,
                   :work_mode, :night_shift, :t, :t)
           ON CONFLICT(id) DO UPDATE SET
               title=excluded.title, company=excluded.company, location=excluded.location,
               url=excluded.url, deadline=excluded.deadline, score=excluded.score,
               categories=excluded.categories, skills=excluded.skills, eligible=excluded.eligible, last_seen=excluded.last_seen,
               night_shift=excluded.night_shift, work_mode=excluded.work_mode""",
        {**{k: job.get(k) for k in ("id", "source", "title", "company", "location", "url", "posted",
                                    "deadline", "experience", "job_type", "salary", "description",
                                    "eligible", "score", "night_shift")},
         "work_mode": job.get("work_mode") or "Remote",
         "categories": json.dumps(job.get("categories", [])),
         "skills": json.dumps(job.get("skills", [])), "t": t},
    )


def reject(con, job_id, reason):
    con.execute("INSERT OR IGNORE INTO seen_rejected (id, reason) VALUES (?, ?)", (job_id, reason))
