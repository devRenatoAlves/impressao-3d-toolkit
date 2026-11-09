---
name: hermes-messaging-bot-visibility
description: "Use when a Hermes messaging bot looks dead or needs on/off."
version: 1.1.0
author: Renato Alves
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [hermes, gateway, telegram, whatsapp, messaging, desktop-plugins, diagnostics]
    related_skills: [hermes-agent, inspecting-hermes-desktop-dom]
---

# Hermes messaging bots — diagnose, toggle, make visible

For "is my Telegram/WhatsApp bot even running?", "where is the connection?",
and "how do I turn the bot on/off?". The common case is an install configured
entirely from the terminal, leaving the user with no way to see state.

---

## When to Use

- A messaging bot (Telegram, WhatsApp, Discord, Slack) stopped answering, or
  the user does not know whether it is running at all.
- "Where is the connection?" / "how do I enable or disable the bot?"
- Adding an always-visible gateway readout to the desktop app.
- After a reboot silently killed a bot that "was working yesterday".

Not for: composing bot replies, or Bot Mode rooms (see `hermes-agent`).

## The one thing to check first: configured != connected

`platform_toolsets` in `config.yaml` lists EVERY platform (`whatsapp:
[hermes-whatsapp]`, …) as a shipped default. **It is not evidence that the
platform is connected.** A user reading that block concludes WhatsApp exists
when no credential was ever set. Always prove it from credentials + live state,
never from `platform_toolsets`.

A platform is live only if it has its credential in `$HERMES_HOME/.env`
(`TELEGRAM_BOT_TOKEN`, `WHATSAPP_ACCESS_TOKEN`, `DISCORD_BOT_TOKEN`, …) AND
appears under `platforms` in `gateway_state.json`.

## Source of truth: gateway_state.json

`$HERMES_HOME/gateway_state.json` is rewritten by the gateway on every
connection change. Prefer it over grepping `logs/gateway.log`:

```json
{ "gateway_state": "running", "active_agents": 1, "restart_requested": false,
  "platforms": { "telegram": { "state": "connected", "needs_attention": false,
                               "error_message": null, "updated_at": "..." } } }
```

States seen in the desktop UI: `connected`, `connecting`, `retrying`,
`degraded`, `pending_restart`, `disabled`, `not_configured`, `error`. The file
keeps no history, so read `logs/gateway.log` ONLY to recover the last error
message. The gateway broadcasts the `platforms.changed` event when it rewrites
the file — subscribe instead of polling hard.

## Turning a bot on/off

`platforms.<name>.enabled: false` in `config.yaml` is the official switch, and
it **wins over a valid credential in `.env`** (`gateway/config_env.py` logs a
one-time warning saying so). The change needs a gateway restart to take
effect; until then the platform reports `pending_restart`.

Three ways, best first:

1. **Desktop app → sidebar → Messaging.** Already ships a per-platform
   `Switch`, state badges, pairing/allowlist approve-revoke, Telegram QR
   onboarding, and a "restart gateway now" button. Users who configured by
   terminal routinely never find this page — point at it before building
   anything. Also reachable via ⌘K "Open messaging" (`nav.messaging` ships
   with NO default keybind) or route `/messaging`.
2. `hermes config set platforms.telegram.enabled false` then
   `hermes gateway restart`.
3. `hermes gateway setup` for first-time wiring.

Never hand-edit `config.yaml`.

## Autostart: the gap that fakes a dead bot

`hermes gateway install` can leave the unit **`disabled`** while it is
`active` — the desktop app started it, so everything looks fine until a
reboot, after which the bot is silently dead. Check both, separately:

```bash
systemctl --user is-enabled hermes-gateway.service   # boot persistence
systemctl --user is-active  hermes-gateway.service   # right now
loginctl show-user "$USER" -p Linger                 # survives logout
```

`systemctl --user enable hermes-gateway.service` fixes the first. `Linger=yes`
is separate and does NOT imply boot start.

## RPC doors a desktop plugin may use — and the two that are shut

| Need | Method | Verdict |
|---|---|---|
| Read status | `shell.exec` `{command}` → `{stdout, stderr, code}` | works; 30 s cap, output redacted |
| `hermes config set …` | `shell.exec` or `cli.exec` | allowed |
| `systemctl … restart/stop` | `shell.exec` | **BLOCKED** "dangerous: stop/restart system service" |
| `hermes gateway restart` | `shell.exec` | **BLOCKED** "kills running agents" |
| `hermes gateway *` | `cli.exec` | **BLOCKED** by `_CLI_EXEC_BLOCKED` (long-running) |

So a plugin can READ freely and flip config, but cannot restart the gateway.
That is correct, not a bug: **the desktop chat itself runs through that same
gateway**, so a plugin-triggered stop would kill the user's live session. Route
restarts to the Messaging page's own button (`runGatewayRestart`, which the app
handles with a reconnect toast). Verify a command's verdict before shipping:

```python
from tools import approval_detection as a   # run inside ~/.hermes/hermes-agent
a.detect_hardline_command(cmd); a.detect_dangerous_command(cmd)
```

## Desktop plugin gotchas (cost real debugging time)

- **No `require`** — the file is ESM loaded uncompiled. `queryClient` is a
  top-level SDK export; importing it lazily with `require()` throws
  `ReferenceError: require is not defined`, logged to `logs/desktop.log` as
  `[plugins] gateway event listener failed`.
- **`PALETTE_AREA` rows need `label`, not `title`** — `{ id, label, run,
  keywords?, detail? }`. A row missing `label` is silently filtered out.
- **`StatusDot` tones are `good | warn | bad | muted`** — use it instead of
  hardcoding green/red, which the no-hardcoded-colour rule forbids.
- **There is no `pt`/`pt-BR` locale** in the desktop app (en, es, fr, de, ja,
  ru, zh, zh-hant, ar). For a pt-BR user running `display.language: en`,
  register the Portuguese bundle under BOTH keys: `ctx.i18n.register({ en: pt,
  pt })`.
- **Don't shadow the `host` SDK import** with a parameter named `host` in an
  i18n interpolator.
- **Packaged builds expose no CDP port**, so the DOM cannot be inspected to
  confirm a pane rendered (`inspecting-hermes-desktop-dom` only works on dev
  servers). Verify by (a) `node --input-type=module --check < plugin.js`,
  (b) grepping every imported identifier against
  `apps/desktop/src/sdk/index.ts`, (c) `logs/desktop.log` for
  `failed to load`, then (d) asking the user to look.
- Standalone `$HERMES_HOME/desktop-plugins/<id>/plugin.js` loads **enabled by
  default** and hot-reloads on save. The `$HERMES_HOME/plugins/<id>/desktop/`
  half is opt-in and needs a toggle flipped — prefer standalone for a simple
  readout.

## Deliverable that exists on this machine

`$HERMES_HOME/bin/status-bots.py` (shell alias `bots`) — gateway service state,
boot persistence, per-platform live state, last error, optional extra TCP probe.
`--json` for machines, `--quick` (~60 ms, no network probe) for polling a
statusbar chip. Prints presence/length of credentials, never values. Falls back
to pid liveness from `gateway_state.json` when `systemctl` is unavailable, so it
never reports "stopped" for a gateway that is up.

`$HERMES_HOME/desktop-plugins/bots-status/plugin.js` — statusbar chip + right
pane reading that script via `shell.exec`, invalidating on `platforms.changed`,
clicking through to the native Messaging page for the actual on/off switch.
Build the script path as `${HERMES_HOME:-$HOME/.hermes}` — hardcoding
`~/.hermes` reads the wrong profile's state under `hermes -p <name>`.

## Cosmetic warnings safe to ignore

`platform 'teams'/'google_chat' has no valid toolsets configured (unknown
name(s): hermes-teams)` — unconfigured platforms; `hermes tools` clears it.
