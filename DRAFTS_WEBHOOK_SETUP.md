# Drafts -> TD Webhook (Direct TD Create)

> Deprecated: this local-LAN webhook flow was replaced by the hosted DigitalOcean queue flow in `DO_DRAFTS_SETUP.md`.

This flow does **not** use Shortcuts and does **not** use CSV/importer launchd.

- On iPhone, create a Draft with one line.
- Run one Drafts Action (`Send to TD`).
- Webhook creates the TD task directly in the right project.

## Live Endpoint (current Mac LAN)
- URL: `http://<your-mac-lan-ip>:8787/capture?token=REPLACE_WITH_REAL_TOKEN`
- Health: `http://192.168.22.241:8787/health`

## Draft Content Format
Use one line:

```text
project|priority|title|notes
```

Examples:
```text
btc|P2|Fix orderbook retry jitter|look at reconnect burst at startup
photos|P3|Update family page copy|short copy cleanup
```

Allowed values:
- `project`: `btc` or `photos`
- `priority`: `P0`, `P1`, `P2`, `P3`

## Drafts Action Setup (iPhone)
1. Open Drafts.
2. Open Action List.
3. Tap `+` to create a new Action.
4. Name: `Send to TD`.
5. Add step: `HTTP Request`.
6. Set:
- Method: `POST`
- URL: `http://<your-mac-lan-ip>:8787/capture?token=REPLACE_WITH_REAL_TOKEN`
- Content Type: `Plain Text`
- Body: `[[draft]]`
7. Optional: add Success/Toast step with text `Queued to TD`.
8. Save action.

## Test
1. Create draft content:
```text
btc|P2|Webhook live test|sent from phone
```
2. Run `Send to TD`.

## Important
- This LAN URL works when phone is on the same network as Mac.
- For away-from-home use, enable Tailscale on Mac+iPhone and replace URL host with Tailscale IP/hostname.
