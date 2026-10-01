# Deploying to Vercel

The web app is a set of Vercel **file-based Python functions** (`api/*.py`)
plus static files in `public/`. The radar chart is rendered in the browser, so
the server bundle does **not** include matplotlib/Pillow.

## 1. Push to GitHub

```bash
git add .
git commit -m "steam-profile web app"
git push
```

## 2. Import into Vercel

- New Project → import the repo.
- **Root Directory**: `skills/steam-profile`
- Framework Preset: **Other** (do not add FastAPI/Flask — that would disable
  the file-based functions and static `public/`).

## 3. Provision Upstash Redis

Add the Upstash Redis integration (Marketplace) or create a database manually,
then copy the REST URL and token into the project env vars.

## 4. Environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `STEAM_API_KEY` | yes | Server-side only. Never exposed to the browser. |
| `UPSTASH_REDIS_REST_URL` | yes | Cache + rate limiting. |
| `UPSTASH_REDIS_REST_TOKEN` | yes | Cache + rate limiting. |
| `SESSION_SECRET` | recommended | Signs the SteamID cookie. |
| `RATE_LIMIT` / `RATE_WINDOW_SECONDS` | no | Defaults `10` / `600`. |
| `STEAM_ID` | no | Single-user default. |

Without Upstash the app still runs, but cache/rate limit fall back to
per-instance memory (lost on cold start).

## 5. Register the domain with Steam

Steam only allows one domain per API key. Register your production domain
(e.g. `my-app.vercel.app`) at https://steamcommunity.com/dev/apikey.

> Steam OpenID only works on the **production** domain. Preview deployments
> (`*-git-*.vercel.app`) will not pass verification.

## 6. Deploy and verify

```bash
curl https://your-app.vercel.app/api/health
curl https://your-app.vercel.app/api/config
```

Then in the browser: open the app, sign in through Steam, generate a profile,
and download the PNG.

## Routes

| Route | Purpose |
| --- | --- |
| `GET /` | Web app (`public/index.html`) |
| `GET /api/health` | Health check |
| `GET /api/config` | API key + SteamID status, defaults, category colors |
| `GET /api/profile` | Run the pipeline (rate limited), returns JSON |
| `GET /api/auth/login` → `/api/auth/callback` | Steam OpenID; sets a signed HttpOnly cookie |

## Local development

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python serve.py        # http://localhost:8000
python -m unittest discover -s tests
```

`serve.py` mirrors the production routes and serves `public/`. It uses the
filesystem cache, or Upstash automatically when its env vars are set.
