---
name: steam-profile
description: >
  Generate a visual Steam gaming profile (radar chart + top games) from a
  user's Steam library. Use when the user asks for a Steam profile, Steam
  Wrapped, a gaming category breakdown, or their most-played games.
version: 0.1.0
entrypoint: generate.py
triggers:
  - "steam profile"
  - "steam wrapped"
  - "gaming profile"
  - "most played games"
  - "steam radar chart"
requires:
  env: [STEAM_API_KEY]
  optional_env: [STEAM_ID]
  bins: [python]
assets:
  - templates/classic.json
  - data/tag_mapping.json
---

# Steam Profile

Generate a "YOU ARE WHAT YOU PLAY" infographic from a user's Steam library.

## When to use

Use this skill when the user asks for any of:

- Steam profile analysis / "buatkan steam profile aku"
- Steam gaming profile / "buatkan steam gaming profile"
- Steam Wrapped
- Most played Steam games
- Gaming category analysis / Steam radar chart

## Inputs

- `STEAM_API_KEY` (required) — a Steam Web API key.
- Steam account, resolved in this order:
  1. `--steamid` argument (SteamID64, profile URL, or vanity name).
  2. `STEAM_ID` environment variable / `config.json` `steam_id`.
  3. Ask the user for a public Steam profile URL or SteamID64.

Never ask for a Steam username/password, and never store credentials.

## How to run

```bash
python generate.py --steamid <id> --out output/steam_profile.png
```

Offline / reproducible runs (uses the cache only):

```bash
python generate.py --steamid <id> --offline
```

Fixtures (no network, used by tests):

```bash
python generate.py --fixture tests/fixtures/owned_games.json --out output/test.png
```

## Web app

```bash
python serve.py        # http://localhost:8000/
```

Static UI in `public/`, API in `api/*.py` (Vercel). The radar is rendered in
the browser and the PNG is exported client-side. In production the SteamID is
kept in a signed HttpOnly cookie, Upstash Redis provides caching + rate
limiting, and `STEAM_API_KEY` stays server-side. See `DEPLOY.md`.

## Outputs

- `<out>.png` — the infographic (default `output/steam_profile.png`).
- `<out>.json` — the deterministic profile payload (categories, top games,
  stats). The JSON is the source of truth; the image is derived from it.

## Configuration

Copy `config.example.json` to `config.json`. Options:

| Key              | Values                              | Default    |
| ---------------- | ----------------------------------- | ---------- |
| `aggregation`    | `weighted`, `full`, `primary`       | `weighted` |
| `scale`          | `linear`, `sqrt`, `log`             | `sqrt`     |
| `metadata_source`| `steamspy`, `store`                 | `steamspy` |
| `top_games`      | integer                             | `5`        |
| `max_categories` | integer                             | `8`        |
| `include_other`  | boolean                             | `true`     |

Secrets go in `.env` (`STEAM_API_KEY`, `STEAM_ID`), never in `config.json`.

## Data source notes

The official Steam Web API exposes appid, name, and playtime only, and
returns no user tags. Tags come from SteamSpy, falling back to the Steam
Store `appdetails` genres. `data/manual_overrides.json` always wins.
Metadata is cached under `cache/` and fetched with backoff; failures
degrade to the `Other` category instead of aborting.

`playtime_forever` is in minutes and is converted to hours at the edge.

## Error handling

- Invalid SteamID -> "I couldn't find that Steam profile..."
- Private game details -> "Your Steam game details appear to be private..."
- API failure -> "Steam data couldn't be retrieved right now..."
- No games -> "No playable games were found for this Steam profile."
- Missing metadata -> the game is counted under `Other`.

## Privacy

Only public Steam data or explicitly configured API credentials are used.
The skill never requests or stores Steam passwords, cookies, or session
tokens.
