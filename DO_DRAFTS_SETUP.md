# Drafts -> DO Endpoint -> Mac TD Puller

This is the active workflow.

## Endpoint
- URL: `https://your-domain/td-capture?token=REPLACE_WITH_REAL_TOKEN`
- Health: `https://your-domain/td-capture/health`

## Draft Format
One line in Drafts:

```text
project@priority@title@notes
```

Examples:
```text
btc@P2@Fix orderbook retry jitter@look at reconnect burst at startup
photos@P3@Update family page copy@short copy cleanup
giftlist@P3@Add birthday idea for dad@hiking boots size 11
```

Allowed:
- `project`: `btc`, `photos`, or `giftlist`
- `priority`: `P0`, `P1`, `P2`, `P3`

## Drafts Action (iPhone)
Create action `Send to TD` with one HTTP Request step:
- Method: `POST`
- URL: `https://your-domain/td-capture?token=REPLACE_WITH_REAL_TOKEN`
- Content Type: `Plain Text`
- Body: `[[draft]]`

Optional 2nd step: show success toast.

## Mac Puller
- Script: `/Users/gaylonvorwaller/td-sync/td_do_puller.py`
- Env: `/Users/gaylonvorwaller/td-sync/td_do_puller.env`
- LaunchAgent: `/Users/gaylonvorwaller/Library/LaunchAgents/com.td.do-puller.plist`
- Interval: 60s

## Quick Checks
```bash
launchctl print gui/$(id -u)/com.td.do-puller | head -n 40
tail -n 80 /Users/gaylonvorwaller/logs/td-importer/td-do-puller.out.log
tail -n 80 /Users/gaylonvorwaller/logs/td-importer/td-do-puller.err.log
```
