#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.parse
from pathlib import Path

HOME = Path('/Users/gaylonvorwaller')
LEDGER = HOME / 'td-sync/td_do_processed_ids.txt'
LOCK = HOME / 'td-sync/td_do_puller.lock'

BASE = os.environ.get('TD_DO_CAPTURE_BASE', 'https://gaylon.photos/td-capture').rstrip('/')
TOKEN = os.environ.get('TD_DO_CAPTURE_TOKEN', '').strip()
LIMIT = int(os.environ.get('TD_DO_PULL_LIMIT', '25'))

TD_BIN = os.environ.get('TD_BIN', shutil.which('td') or '/Users/gaylonvorwaller/go/bin/td')
ISSUE_RE = re.compile(r'\b(td-[a-z0-9]+)\b', re.IGNORECASE)

PROJECT_MAP = {
    'btc': '/Users/gaylonvorwaller/BTC-dashboard',
    'photos': '/Users/gaylonvorwaller/gaylonphotos',
    'giftlist': '/Users/gaylonvorwaller/giftlist',
}

PRIORITIES = {'P0', 'P1', 'P2', 'P3'}


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def normalize_title(title: str) -> str:
    t = (title or '').strip()
    if len(t) >= 15:
        return t
    # td requires at least 15 chars for issue titles.
    # Use neutral punctuation padding to avoid repeating words like "task task task".
    padded = f"{t} {'.' * max(1, 15 - len(t))}"
    return padded[:100]


def load_ledger() -> set[int]:
    if not LEDGER.exists():
        return set()
    ids = set()
    with LEDGER.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.isdigit():
                ids.add(int(line))
    return ids


def append_ledger(ids: list[int]) -> None:
    if not ids:
        return
    ensure_parent(LEDGER)
    with LEDGER.open('a', encoding='utf-8') as f:
        for i in ids:
            f.write(f'{i}\n')


def request_json(method: str, url: str, payload: dict | None = None) -> dict:
    cmd = [
        'curl',
        '-fsS',
        '-X',
        method,
        url,
        '-H',
        f'Authorization: Bearer {TOKEN}',
        '-H',
        'Accept: application/json',
        '-H',
        'User-Agent: td-do-puller/1.0',
    ]
    if payload is not None:
        cmd.extend(['-H', 'Content-Type: application/json', '--data', json.dumps(payload)])
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or 'curl request failed').strip())
    return json.loads((p.stdout or '{}').strip())


def td_create(project: str, priority: str, title: str, notes: str) -> str:
    cmd = [TD_BIN, '-w', project, 'create', title, '-t', 'task', '-p', priority]
    if notes:
        cmd.extend(['--description', notes])
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = ((p.stdout or '') + '\n' + (p.stderr or '')).strip()
    if p.returncode != 0:
        raise RuntimeError(out or 'td create failed')
    m = ISSUE_RE.search(out)
    return m.group(1) if m else ''


def main() -> int:
    if not TOKEN:
        print('missing TD_DO_CAPTURE_TOKEN')
        return 2

    ensure_parent(LOCK)
    with LOCK.open('w', encoding='utf-8') as lockf:
        try:
            import fcntl
            fcntl.flock(lockf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:
            print('another td_do_puller run is active; exiting')
            return 0

        pull_url = f"{BASE}/pull?{urllib.parse.urlencode({'limit': LIMIT})}"
        data = request_json('GET', pull_url)
        items = data.get('items', []) or []

        if not items:
            print('pulled=0 created=0 acked=0 failed=0')
            return 0

        seen = load_ledger()
        ack_ids: list[int] = []
        new_ids: list[int] = []
        failures = 0
        created = 0

        for item in items:
            item_id = int(item.get('id', 0) or 0)
            if not item_id:
                continue
            if item_id in seen:
                ack_ids.append(item_id)
                continue

            project_key = str(item.get('project', '')).strip().lower()
            priority = str(item.get('priority', '')).strip().upper()
            title = normalize_title(str(item.get('title', '')).strip())
            notes = str(item.get('notes', '')).strip()

            project_dir = PROJECT_MAP.get(project_key, '')
            if not project_dir or priority not in PRIORITIES or not title:
                failures += 1
                continue

            try:
                issue_id = td_create(project_dir, priority, title, notes)
                created += 1
                ack_ids.append(item_id)
                new_ids.append(item_id)
                print(f'created item={item_id} issue={issue_id} project={project_key} priority={priority}')
            except Exception as e:  # noqa: BLE001
                failures += 1
                print(f'failed item={item_id}: {e}')

        if ack_ids:
            request_json('POST', f'{BASE}/ack', {'ids': ack_ids})
        if failures:
            request_json('POST', f'{BASE}/requeue', {})

        append_ledger(new_ids)
        print(f'pulled={len(items)} created={created} acked={len(ack_ids)} failed={failures}')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
