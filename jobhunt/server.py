"""Local app: `python -m jobhunt.server` then open http://localhost:8765"""
import json
import os
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import cv, db, scrape, store

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
PORT = int(os.environ.get("JOBHUNT_PORT") or 8765)
STATUSES = {"new", "saved", "applied", "interview", "rejected", "hidden"}

con = db.connect()
lock = threading.Lock()
scrape_state = {"running": False, "log": [], "finished": None}


def run_scrape():
    def log(msg):
        scrape_state["log"].append(msg)
        print(msg)
    scrape_state.update(running=True, log=[])
    try:
        scrape.run(log=log)
    except Exception as e:
        log(f"Error: {e}")
    finally:
        scrape_state.update(running=False, finished=datetime.now().isoformat(timespec="seconds"))


def setup_done():
    p, c = store.load_profile(), store.load_criteria()
    return bool(p and p.get("complete") and c and c.get("complete"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json", headers=None):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, to):
        self.send_response(302)
        self.send_header("Location", to)
        self.end_headers()

    def _page(self, name):
        return self._send(200, (STATIC / name).read_bytes(), "text/html; charset=utf-8")

    def do_GET(self):
        url = urlparse(self.path)
        path, query = url.path, parse_qs(url.query)
        if path == "/":
            return self._page("index.html") if setup_done() else self._redirect("/setup")
        if path == "/setup":
            return self._page("setup.html")
        if path == "/api/state":
            with lock:
                count = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            return self._send(200, {
                "profile": store.load_profile(), "criteria": store.load_criteria(),
                "defaults": {"profile": store.DEFAULT_PROFILE, "criteria": store.DEFAULT_CRITERIA},
                "jobs": count, "scraping": scrape_state["running"]})
        if path == "/api/jobs":
            with lock:
                rows = [dict(r) for r in con.execute(
                    "SELECT id, source, title, company, location, url, posted, deadline, experience, job_type,"
                    " salary, eligible, score, categories, skills, status, notes, first_seen, work_mode, night_shift"
                    " FROM jobs")]
            for r in rows:
                r["categories"] = json.loads(r["categories"] or "[]")
                r["skills"] = json.loads(r["skills"] or "[]")
            return self._send(200, rows)
        if path == "/api/job":
            jid = query.get("id", [""])[0]
            with lock:
                row = con.execute("SELECT description FROM jobs WHERE id=?", (jid,)).fetchone()
            return self._send(200, {"description": row["description"] if row else ""})
        if path == "/api/scrape":
            return self._send(200, scrape_state)
        if path in ("/cv.pdf", "/cv.docx"):
            profile = store.load_profile()
            if not profile:
                return self._send(404, {"error": "Build your CV first."})
            ext = path.rsplit(".", 1)[1]
            try:
                body = cv.pdf_bytes(profile) if ext == "pdf" else cv.docx_bytes(profile)
            except Exception as e:
                return self._send(500, {"error": f"Couldn't build the CV: {e}"})
            ctype = "application/pdf" if ext == "pdf" else \
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            disp = "attachment" if query.get("download") or ext == "docx" else "inline"
            name = cv.filename(profile, ext)
            return self._send(200, body, ctype,
                              {"Content-Disposition": f"{disp}; filename=\"{name}\"; filename*=UTF-8''{quote(name)}"})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self._send(400, {"error": "bad json"})
        if path == "/api/profile":
            return self._send(200, store.save_profile(body))
        if path == "/api/criteria":
            saved = store.save_criteria(body)
            removed = 0
            # Autosaves during first-time setup don't touch stored jobs; an explicit save does.
            if body.get("apply") and saved.get("complete") and saved.get("roles"):
                with lock:
                    db.sync_criteria(con)
                    removed = scrape.rescore(log=lambda *_: None)
                    con.commit()
            return self._send(200, {"criteria": saved, "removed": removed})
        if path == "/api/update":
            fields = {k: v for k, v in body.items() if k in ("status", "notes")}
            if "status" in fields and fields["status"] not in STATUSES:
                return self._send(400, {"error": "bad status"})
            if not fields:
                return self._send(400, {"error": "nothing to update"})
            with lock:
                con.execute(f"UPDATE jobs SET {', '.join(f'{k}=?' for k in fields)} WHERE id=?",
                            (*fields.values(), body["id"]))
                con.commit()
            return self._send(200, {"ok": True})
        if path == "/api/scrape":
            if not scrape_state["running"]:
                threading.Thread(target=run_scrape, daemon=True).start()
            return self._send(200, {"ok": True})
        self._send(404, {"error": "not found"})


def main():
    url = f"http://localhost:{PORT}"
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print(f"Job Hunt is already running. Opening {url}")
        webbrowser.open(url)
        sys.exit(0)
    print(f"Job Hunt is running at {url}")
    print("Keep this window open while you use it. Close it (or press Ctrl+C) to stop.")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
