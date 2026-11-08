"""Small SQLite store. Holds sessions, consent records, orders and hand-offs.
Document images are never written here; only extracted, masked-for-logs fields."""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import DB_PATH

_lock = threading.Lock()

SCHEMA = """
create table if not exists sessions(id text primary key, updated text, data text);
create table if not exists consents(id integer primary key autoincrement, session_id text, ts text,
  version text, language text, purposes text, granted integer);
create table if not exists orders(id text primary key, session_id text, updated text, data text);
create table if not exists handoffs(id integer primary key autoincrement, session_id text, ts text,
  reason text, summary text, status text default 'open');
create table if not exists audit(id integer primary key autoincrement, ts text, session_id text, event text, detail text);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def conn():
    with _lock:
        c = sqlite3.connect(DB_PATH, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.executescript(SCHEMA)
        try:
            yield c
            c.commit()
        finally:
            c.close()


def save_session(s: dict) -> None:
    with conn() as c:
        c.execute("insert or replace into sessions values(?,?,?)", (s["id"], now(), json.dumps(s, ensure_ascii=False)))


_update_lock = threading.RLock()


def update_session(sid: str, fn) -> dict | None:
    """Atomic read-modify-write. Slow tasks (LLM, OCR) must use this to store their result, never save a
    session object they loaded before the slow work started: that erases changes made in the meantime."""
    with _update_lock:
        s = load_session(sid)
        if s is None:
            return None
        fn(s)
        save_session(s)
        return s


def load_session(sid: str) -> dict | None:
    with conn() as c:
        r = c.execute("select data from sessions where id=?", (sid,)).fetchone()
    return json.loads(r["data"]) if r else None


def save_order(o: dict) -> None:
    with conn() as c:
        c.execute("insert or replace into orders values(?,?,?,?)",
                  (o["id"], o["session_id"], now(), json.dumps(o, ensure_ascii=False)))


def load_order(oid: str) -> dict | None:
    with conn() as c:
        r = c.execute("select data from orders where id=?", (oid,)).fetchone()
    return json.loads(r["data"]) if r else None


def add_consent(session_id: str, version: str, language: str, purposes: list[str], granted: bool) -> None:
    with conn() as c:
        c.execute("insert into consents(session_id,ts,version,language,purposes,granted) values(?,?,?,?,?,?)",
                  (session_id, now(), version, language, json.dumps(purposes), int(granted)))


def add_handoff(session_id: str, reason: str, summary: dict) -> None:
    with conn() as c:
        dup = c.execute("select 1 from handoffs where session_id=? and reason=?", (session_id, reason)).fetchone()
        if not dup:
            c.execute("insert into handoffs(session_id,ts,reason,summary) values(?,?,?,?)",
                      (session_id, now(), reason, json.dumps(summary, ensure_ascii=False)))


def list_handoffs() -> list[dict]:
    with conn() as c:
        rows = c.execute("select * from handoffs order by id desc limit 200").fetchall()
    return [{**dict(r), "summary": json.loads(r["summary"])} for r in rows]


def audit(session_id: str | None, event: str, detail: str = "") -> None:
    with conn() as c:
        c.execute("insert into audit(ts,session_id,event,detail) values(?,?,?,?)", (now(), session_id, event, detail))
