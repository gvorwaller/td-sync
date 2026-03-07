# TD Mobile Capture Bridge

Capture `td` tasks from iPhone (Drafts) and ingest them into local project-specific `td` databases on Mac.

## Overview

This project provides a lightweight bridge:

1. iPhone Drafts sends task text to a hosted HTTPS endpoint.
2. DigitalOcean endpoint queues items (`btc` or `photos`).
3. Mac `launchd` puller polls queue, runs `td create` in correct project dir, and ACKs processed items.

This avoids exposing your Mac directly to the internet and works well with intermittent Mac availability.

## Message Format

Draft content format:

```text
project@priority@title@notes
```

Examples:

```text
btc@P2@Fix reconnect jitter@check startup burst behavior
photos@P1@Update itinerary map line@line still missing in some cases
```

Rules:
- `project`: `btc` or `photos`
- `priority`: `P0`, `P1`, `P2`, `P3`
- `title`: `td` requires minimum 15 characters (puller pads short titles)

## Components

- `td_do_puller.py`: Mac queue consumer + `td create` executor.
- `drafts_send_to_td.js`: Drafts action script (POST to endpoint).
- `td_do_puller.env`: local runtime config (endpoint/token/pull limit). **Secret**.
- `DO_DRAFTS_SETUP.md`: operator notes for iPhone action setup.

## Mac Setup

1. Ensure `td` CLI is installed and project DBs exist.
2. Configure `td_do_puller.env`:

```bash
TD_DO_CAPTURE_BASE=https://your-domain/td-capture
TD_DO_CAPTURE_TOKEN=<SECRET_TOKEN>
TD_DO_PULL_LIMIT=25
```

3. Load launch agent:

```bash
launchctl bootstrap gui/$(id -u) /Users/<you>/Library/LaunchAgents/com.td.do-puller.plist
launchctl kickstart -k gui/$(id -u)/com.td.do-puller
```

4. Verify:

```bash
launchctl print gui/$(id -u)/com.td.do-puller | head -n 40
tail -n 80 /Users/<you>/logs/td-importer/td-do-puller.out.log
tail -n 80 /Users/<you>/logs/td-importer/td-do-puller.err.log
```

## Drafts Setup (iPhone)

Create action `Send to td` with one **Run JavaScript** step.

`drafts_send_to_td.js` expects a tokenized endpoint:

```javascript
let endpoint = "https://your-domain/td-capture?token=<SECRET_TOKEN>";
```

Then run action on a draft using the `project@priority@title@notes` format.

## Queue API (Hosted)

Expected endpoints:
- `POST /td-capture` or `/td-capture/enqueue`
- `GET /td-capture/pull?limit=N`
- `POST /td-capture/ack`
- `POST /td-capture/requeue`
- `GET /td-capture/health`

## Security Notes (Before GitHub Push)

- Do **not** commit live tokens in:
  - `td_do_puller.env`
  - `drafts_send_to_td.js`
  - setup docs with tokenized URLs
- Rotate token if previously exposed in screenshots/chats.
- Prefer placeholder values in docs and local-only secret files.

## Operational Notes

- Puller uses file lock to avoid concurrent runs.
- On transient failures, items are requeued.
- Successfully processed IDs are recorded in `td_do_processed_ids.txt`.

## Troubleshooting

- `HTTP 401 unauthorized`: token mismatch between Drafts/Mac and hosted endpoint.
- `pulled=0` repeatedly: queue empty or wrong token.
- No task created: check `td-do-puller.err.log` and title length/priority/project values.

