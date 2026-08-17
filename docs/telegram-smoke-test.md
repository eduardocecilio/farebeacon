# Telegram smoke test

This runbook proves that a real Telegram message leaves FareBeacon, that the alert event records the
provider receipt, and that replaying the delivery does not produce a second message. Automated tests
cover the adapter with a mocked transport and the asynchronous path with `FakeNotifier`; only this
procedure exercises the official Bot API.

## Safety boundary

- The bot token and chat id are credentials. They never belong in source, issues, pull requests,
  commit messages, shell history, container command lines, or captured evidence.
- Run the procedure against a disposable stack, never against a deployment that owns real history.
- If a result is ambiguous, stop and preserve the alert event state instead of retrying. A second
  attempt on an ambiguous state can produce a duplicate Telegram message, because `sendMessage` has
  no idempotency key.

## Prerequisites

- Docker Engine with Compose v2 on an ephemeral acceptance host, per the boundary in
  [operations](operations.md).
- A Telegram account that will receive the alert.
- `curl` and `jq`.

## 1. Create a disposable bot

1. Open `@BotFather` in Telegram and send `/newbot`.
2. Choose a display name and a username ending in `bot`, for example `farebeacon_smoke_bot`.
3. Copy the token that `@BotFather` returns. Treat it as a password.

Keep the token in the environment of the current shell only:

```bash
read -rs FAREBEACON_TELEGRAM_BOT_TOKEN
export FAREBEACON_TELEGRAM_BOT_TOKEN
```

`read -rs` keeps the value off the terminal and out of shell history.

## 2. Start the conversation

Open the new bot from the destination account and press **Start** once. A bot cannot message a user
who has never started the conversation; skipping this step produces HTTP 403 later.

## 3. Discover the numeric chat id

The token belongs in the request URL, so build the request from standard input instead of the
command line. `curl --config -` reads the URL from a file descriptor, which keeps the token out of
`argv` and out of the process title:

```bash
curl -sS --config - <<EOF | jq '[.result[] | (.message // .edited_message).chat? // empty] | unique'
url = "https://api.telegram.org/bot${FAREBEACON_TELEGRAM_BOT_TOKEN}/getUpdates"
EOF
```

Export the private chat's numeric `id`:

```bash
export FAREBEACON_TELEGRAM_CHAT_ID='the-numeric-id'
```

If `result` is empty, send any message to the bot and repeat. If the call returns HTTP 409, a
webhook is registered; delete it with the same stdin pattern against `deleteWebhook` before
retrying.

## 4. Start an isolated stack

Use a dedicated Compose project name so the smoke test never shares volumes with another stack:

```bash
export COMPOSE_PROJECT_NAME=farebeacon-smoke
cp .env.example .env
chmod 600 .env
```

Edit `.env` and set every value the run needs:

```dotenv
FAREBEACON_API_TOKEN=a-fresh-random-token-of-at-least-32-characters
FAREBEACON_POSTGRES_PASSWORD=a-fresh-random-database-password
FAREBEACON_NOTIFICATION_BACKEND=telegram
FAREBEACON_TELEGRAM_BOT_TOKEN=the-token-from-botfather
FAREBEACON_TELEGRAM_CHAT_ID=the-numeric-chat-id
FAREBEACON_DEFAULT_ALERT_COOLDOWN_MINUTES=1440
```

`.env` is already ignored by Git. The token reaches only `notification-worker`, the single
application service attached to the egress network.

```bash
docker compose up --build -d
docker compose ps
curl -sS http://127.0.0.1:8000/ready
export FAREBEACON_TOKEN='the-value-of-FAREBEACON_API_TOKEN'
```

## 5. Trigger one deterministic alert

Create a monitor whose only rule is `price_below_limit`, with a limit safely above every price
MockSource can produce for this route. `new_historical_low` is left off on purpose: it never matches
on a first run, and enabling both rules would make the expected message count ambiguous.

```bash
MONITOR_ID=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/monitors \
  -H "Authorization: Bearer $FAREBEACON_TOKEN" \
  -H 'Idempotency-Key: telegram-smoke-monitor-v1' \
  -H 'Content-Type: application/json' \
  --data @- <<'JSON' | jq -r '.data.id'
{
  "name": "Telegram smoke test",
  "route": {"origin": "BSB", "destination": "PVH"},
  "departure_dates": ["2030-07-10"],
  "passengers": {"adults": 1, "children": 0, "infants": 0},
  "filters": {"currency": "BRL", "max_stops": 1, "max_price_minor": 100000},
  "sources": ["mock"],
  "source_configuration": {"mock": {"base_price_minor": 50000}},
  "schedule": {"interval_minutes": 720},
  "alerts": {"price_below_minor": 90000}
}
JSON
)
```

Start exactly one run:

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/monitors/$MONITOR_ID/runs" \
  -H "Authorization: Bearer $FAREBEACON_TOKEN" \
  -H 'Idempotency-Key: telegram-smoke-run-1' | jq '.data'
```

MockSource returns two offers around 50,000 minor units plus a deterministic per-route variation
below 12,000, so the cheapest observation is always under the 90,000 limit and the rule matches on
the first run.

## 6. Verify the delivery

The message must arrive in the private chat, and the alert event must agree with it:

```bash
curl -sS "http://127.0.0.1:8000/api/v1/alerts?monitor_id=$MONITOR_ID" \
  -H "Authorization: Bearer $FAREBEACON_TOKEN" \
  | jq '.data | {total, items: [.items[] | {id, status, provider, provider_message_id, attempt_count}]}'
```

Expected result:

- `total` is 1;
- `status` is `sent`;
- `provider` is `telegram`;
- `provider_message_id` is the numeric Telegram message id;
- `attempt_count` is 1.

A `suppressed` event means the backend was still `disabled` or a cooldown was active. A `failed`
event carries `error_message`; see the diagnosis table below.

## 7. Verify that a replay does not duplicate the message

Delivery is claim-before-send: the worker moves `pending` to `sending` in one atomic statement, so a
replayed task observes a status it cannot claim and returns without calling Telegram.

```bash
ALERT_ID='the-id-from-the-previous-step'
docker compose exec -T notification-worker python - <<PY
from farebeacon.tasks.alerts import dispatch_alert_event
print(dispatch_alert_event("$ALERT_ID"))
PY
```

Expected result: the task reports `sent`, no new message appears in Telegram, and `attempt_count`
stays 1 when the alert is read again.

A second identical run is also expected to stay silent: the rule cooldown records the new event as
`suppressed`, with `suppression_reason` naming the cooldown window.

## 8. Confirm that no credential leaked

Check the captured logs for the token without passing it on a command line. `grep -f -` reads the
pattern from standard input:

```bash
docker compose logs --no-color > /tmp/farebeacon-smoke.log
grep -c -F -f - /tmp/farebeacon-smoke.log <<EOF
${FAREBEACON_TELEGRAM_BOT_TOKEN}
EOF
rm -f /tmp/farebeacon-smoke.log
```

The count must be 0. Repeat the check against any evidence file kept for the record. Screenshots may
show the alert message and the chat, never `@BotFather`'s token message.

## 9. Diagnose Bot API failures

`TelegramNotifier` raises on any non-200 response, and the worker records the event as `failed` with
the HTTP status in `error_message`.

| Symptom | Usual cause | Action |
| --- | --- | --- |
| HTTP 401 | Token is wrong, revoked, or truncated in the environment | Re-read the token, restart `notification-worker`, retry |
| HTTP 400, `chat not found` | `FAREBEACON_TELEGRAM_CHAT_ID` is not the numeric id of a chat the bot can see | Repeat step 3 and use the numeric `id` |
| HTTP 403, `bot was blocked` | The destination never pressed **Start**, or blocked the bot | Repeat step 2 |
| HTTP 429 | Bot API rate limit | Wait for the `retry_after` interval before the next run |
| HTTP 409 on `getUpdates` | A webhook is registered for the bot | Call `deleteWebhook`, then repeat step 3 |
| `Telegram request failed` | DNS, egress, or timeout on the egress network | Check that `notification-worker` reaches `api.telegram.org` |

Failed events are not replayed automatically, and `dispatch_alert_event` only claims `pending`
events, so a failed event is terminal for this release. Fix the cause and start a new run, which
evaluates a new event under a new deduplication key. Explicit reconciliation of failed and stale
deliveries is tracked separately in the backlog.

## 10. Rotate and clean up

```bash
docker compose down -v --remove-orphans
rm -f .env
unset FAREBEACON_TELEGRAM_BOT_TOKEN FAREBEACON_TELEGRAM_CHAT_ID FAREBEACON_TOKEN
```

Then, in `@BotFather`:

- send `/revoke` to invalidate the token used during the test;
- send `/deletebot` when the bot was created only for this smoke test.

Rotate the token immediately, without waiting for cleanup, if it ever appeared in a log, a paste, a
screenshot, or a shared file. On a shared acceptance host, also remove the images that the test
built.
