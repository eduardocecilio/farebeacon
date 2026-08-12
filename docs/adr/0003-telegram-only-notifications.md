# ADR 0003: Telegram is the only real notification channel

Status: accepted

## Decision

FareBeacon supports Telegram through the official Bot API. The core depends on a `Notifier` port,
with `FakeNotifier` for tests and `TelegramNotifier` as the only real adapter.

GOWA, WhatsApp Web multi-device sessions, and similar unofficial gateways are outside both the
implementation and roadmap. FareBeacon will not ship a GOWA container, profile, adapter, or future
phase placeholder.

The self-hosted single-tenant release uses one bot token and one destination chat id from deployment
secrets. A Telegram user presses **Start** once so the bot may message that chat. FareBeacon never
receives the user's password, phone number, or personal Telegram session.

## Consequences

- setup is a bot token plus chat id rather than a linked phone session and persistent QR pairing;
- only the notification worker receives the token and internet egress;
- automatic recipient linking needs a separate authenticated, one-time flow before a future UI can
  safely offer it;
- provider delivery is claim-before-send and not automatically replayed after an ambiguous crash,
  because Telegram's `sendMessage` operation has no idempotency key.
