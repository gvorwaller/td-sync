#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt
import json
import os
import sqlite3
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = os.environ.get('TD_CAPTURE_DB', '/opt/td-capture/queue.db')
TOKEN = os.environ.get('TD_CAPTURE_TOKEN', '').strip()
PORT = int(os.environ.get('TD_CAPTURE_PORT', '8788'))
LOCK = threading.Lock()


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS inbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                project TEXT NOT NULL,
                priority TEXT NOT NULL,
                title TEXT NOT NULL,
                notes TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'drafts',
                state TEXT NOT NULL DEFAULT 'queued',
                claimed_at TEXT,
                processed_at TEXT,
                error TEXT
            )
            '''
        )
        conn.execute('CREATE INDEX IF NOT EXISTS idx_inbox_state_id ON inbox(state, id)')


def parse_plain(body: str) -> dict:
    parts = [p.strip() for p in body.split('|', 3)]
    if len(parts) < 3:
        raise ValueError('plain text format must be project|priority|title|notes(optional)')
    return {
        'project': parts[0],
        'priority': parts[1],
        'title': parts[2],
        'notes': parts[3] if len(parts) >= 4 else '',
    }


def parse_payload(content_type: str, raw: bytes) -> dict:
    body = raw.decode('utf-8', errors='replace').strip()
    ctype = (content_type or '').split(';', 1)[0].strip().lower()
    if ctype == 'application/json':
        data = json.loads(body or '{}')
        return {
            'project': str(data.get('project', '')).strip(),
            'priority': str(data.get('priority', '')).strip(),
            'title': str(data.get('title', '')).strip(),
            'notes': str(data.get('notes', '')).strip(),
        }
    if ctype == 'application/x-www-form-urlencoded':
        p = urllib.parse.parse_qs(body, keep_blank_values=True)
        return {
            'project': (p.get('project', [''])[0] or '').strip(),
            'priority': (p.get('priority', [''])[0] or '').strip(),
            'title': (p.get('title', [''])[0] or '').strip(),
            'notes': (p.get('notes', [''])[0] or '').strip(),
        }
    return parse_plain(body)


class Handler(BaseHTTPRequestHandler):
    server_version = 'TDCapture/1.0'

    def _json(self, code: int, payload: dict) -> None:
        b = json.dumps(payload).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _auth_ok(self) -> bool:
        if not TOKEN:
            return False
        auth = (self.headers.get('Authorization') or '').strip()
        if auth.lower().startswith('bearer '):
            return auth[7:].strip() == TOKEN
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        return (q.get('token', [''])[0] or '').strip() == TOKEN

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ('/health', '/td-capture/health'):
            return self._json(200, {'ok': True, 'service': 'td-capture'})
        if parsed.path == '/td-capture/pull':
            if not self._auth_ok():
                return self._json(401, {'ok': False, 'error': 'unauthorized'})
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                limit = max(1, min(100, int((qs.get('limit', ['25'])[0] or '25'))))
            except ValueError:
                limit = 25
            with LOCK, db() as conn:
                rows = conn.execute(
                    "SELECT id, created_at, project, priority, title, notes FROM inbox WHERE state='queued' ORDER BY id ASC LIMIT ?",
                    (limit,),
                ).fetchall()
                ids = [r['id'] for r in rows]
                if ids:
                    now = now_utc()
                    conn.executemany(
                        "UPDATE inbox SET state='claimed', claimed_at=? WHERE id=? AND state='queued'",
                        [(now, i) for i in ids],
                    )
            items = [dict(r) for r in rows]
            return self._json(200, {'ok': True, 'items': items})
        return self._json(404, {'ok': False, 'error': 'not found'})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ('/td-capture', '/td-capture/enqueue'):
            if not self._auth_ok():
                return self._json(401, {'ok': False, 'error': 'unauthorized'})
            length = int(self.headers.get('Content-Length', '0') or '0')
            raw = self.rfile.read(length)
            try:
                payload = parse_payload(self.headers.get('Content-Type', ''), raw)
            except Exception as e:
                return self._json(400, {'ok': False, 'error': f'bad payload: {e}'})
            project = payload.get('project', '').strip().lower()
            priority = payload.get('priority', '').strip().upper()
            title = payload.get('title', '').strip()
            notes = payload.get('notes', '').strip()
            if project not in {'btc', 'photos', 'giftlist', 'gmailwiz'}:
                return self._json(400, {'ok': False, 'error': 'project must be btc, photos, giftlist, or gmailwiz'})
            if priority not in {'P0', 'P1', 'P2', 'P3'}:
                return self._json(400, {'ok': False, 'error': 'priority must be P0..P3'})
            if not title:
                return self._json(400, {'ok': False, 'error': 'title required'})
            with LOCK, db() as conn:
                cur = conn.execute(
                    'INSERT INTO inbox(created_at, project, priority, title, notes) VALUES (?, ?, ?, ?, ?)',
                    (now_utc(), project, priority, title, notes),
                )
                row_id = cur.lastrowid
            return self._json(201, {'ok': True, 'id': row_id})

        if parsed.path == '/td-capture/ack':
            if not self._auth_ok():
                return self._json(401, {'ok': False, 'error': 'unauthorized'})
            length = int(self.headers.get('Content-Length', '0') or '0')
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode('utf-8') or '{}')
            except Exception:
                return self._json(400, {'ok': False, 'error': 'invalid json'})
            ids = payload.get('ids') or []
            if not isinstance(ids, list):
                return self._json(400, {'ok': False, 'error': 'ids must be list'})
            ids = [int(x) for x in ids if str(x).isdigit()]
            if not ids:
                return self._json(200, {'ok': True, 'acked': 0})
            with LOCK, db() as conn:
                now = now_utc()
                conn.executemany(
                    "UPDATE inbox SET state='done', processed_at=? WHERE id=? AND state IN ('claimed','queued')",
                    [(now, i) for i in ids],
                )
            return self._json(200, {'ok': True, 'acked': len(ids)})

        if parsed.path == '/td-capture/requeue':
            if not self._auth_ok():
                return self._json(401, {'ok': False, 'error': 'unauthorized'})
            with LOCK, db() as conn:
                conn.execute("UPDATE inbox SET state='queued' WHERE state='claimed'")
            return self._json(200, {'ok': True})

        return self._json(404, {'ok': False, 'error': 'not found'})

    def log_message(self, fmt, *args):
        return


if __name__ == '__main__':
    init_db()
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    srv.serve_forever()
