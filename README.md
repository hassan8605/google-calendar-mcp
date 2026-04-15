# Google Calendar MCP

A **Model Context Protocol (MCP) server** for Google Calendar built with Python, FastAPI, and Claude (Anthropic). Users connect their own Google Calendar via OAuth and schedule events using plain English.

```
POST /api/calendar/schedule
{
  "user_id": "hassan",
  "message": "Schedule a 1-hour team standup tomorrow at 10am",
  "timezone": "Asia/Karachi"
}
```

Claude interprets the message, calls Google Calendar tools internally, and creates the event.

---

## What it does

- **Natural language scheduling** — Claude parses intent and calls Google Calendar API
- **Google Meet links** — automatically generates a Meet video conference link when requested
- **Multi-user** — each user connects their own Google Calendar via OAuth
- **MCP server** — Claude Desktop can connect directly and use calendar tools
- **10 calendar tools** — list, search, create, update, delete events, check availability, and more
- **Docker-first** — single `make up` command to run everything

---

## Architecture

```
User / Client App
      │
      ▼
FastAPI (port 4325)
      │
      ├── POST /api/calendar/schedule   ← NLP endpoint
      │         │
      │         ▼
      │    Anthropic Claude
      │    (tool-use loop)
      │         │
      │         ▼
      │    Google Calendar API
      │    (user's own calendar)
      │
      ├── GET  /api/calendar/auth/start     ← OAuth flow
      ├── GET  /api/calendar/auth/callback
      ├── GET  /api/calendar/auth/status
      ├── DELETE /api/calendar/auth/logout
      ├── GET  /api/calendar/users
      │
      └── GET  /mcp/sse   ← Claude Desktop connects here
```

---

## Prerequisites

- [Docker](https://www.docker.com/get-started/) — **recommended way to run**
- [ngrok](https://ngrok.com/) — for testing with multiple users via public URL (optional)
- Google Cloud account (free)
- Anthropic API key — [console.anthropic.com](https://console.anthropic.com)

---

## Step 1 — Get an Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in
3. Go to **API Keys** → **Create Key**
4. Copy the key — you'll add it to `.env` as `ANTHROPIC_API_KEY`

---

## Step 2 — Set up Google Cloud

### 2a. Create a project and enable the API

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use an existing one)
3. Go to **APIs & Services → Library**
4. Search **"Google Calendar API"** → click **Enable**

### 2b. Configure the OAuth consent screen

1. Go to **Google Auth Platform** (or **APIs & Services → OAuth consent screen**)
2. Click **Get Started** (or go to **Branding**)
3. Fill in:
   - **App name**: your app name (e.g. "Calendar MCP")
   - **User support email**: your email
   - **Developer contact email**: your email
4. Go to **Audience** → select **External**
5. Save

### 2c. Create OAuth credentials

1. Go to **Clients** → **+ Create Client**
2. Application type → **Web application**
3. Under **Authorized redirect URIs**, add:
   ```
   http://localhost:4325/api/calendar/auth/callback
   ```
   > If using ngrok, also add your ngrok URL (see ngrok section below)
4. Click **Create**
5. Copy the **Client ID** and **Client Secret**

### 2d. Add test users (Testing mode only)

While your app is in Testing mode, only manually added emails can authorize.

1. Go to **Audience** → scroll to **Test users**
2. Click **+ Add Users**
3. Add every email address that will test the app
4. Click **Save**

> **In production** — publish your app (see Production section below) and this step is not needed.

---

## Step 3 — Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-sonnet-4-6

# Google Calendar
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:4325/api/calendar/auth/callback
```

Leave everything else as-is for local Docker usage.

---

## Step 4 — Run with Docker (recommended)

```bash
make up
```

This builds the image and starts the container on port **4325**.

Check it's running:
```bash
make logs
# or
curl http://localhost:4325/health
```

### All Makefile commands

| Command | Description |
|---|---|
| `make up` | Build image and start container |
| `make down` | Stop and remove container |
| `make restart` | Restart the container |
| `make logs` | Stream container logs |
| `make shell` | Open a bash shell inside the container |
| `make ps` | Show running containers |
| `make clean` | Stop container and remove volumes (**wipes all tokens!**) |
| `make dev` | Run locally without Docker (auto-reload) |
| `make sync` | Install / sync Python dependencies |

---

## Step 5 — Connect a user's Google Calendar

Each user goes through a one-time OAuth flow.

**1. Get the auth URL:**
```
GET http://localhost:4325/api/calendar/auth/start?user_id=hassan
```

Response:
```json
{
  "data": {
    "auth_url": "https://accounts.google.com/o/oauth2/auth?...",
    "user_id": "hassan"
  }
}
```

**2. Open `auth_url` in a browser** → sign in with Google → click Allow

**3. Google redirects to `/auth/callback` automatically** — token is saved.

**4. Verify it worked:**
```
GET http://localhost:4325/api/calendar/auth/status?user_id=hassan
```
```json
{ "data": { "authenticated": true, "user_id": "hassan" } }
```

---

## Step 6 — Schedule via natural language

```bash
curl -X POST http://localhost:4325/api/calendar/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hassan",
    "message": "Schedule a 1-hour meeting with the team tomorrow at 3pm",
    "timezone": "Asia/Karachi"
  }'
```

Claude will:
1. Call `get_current_time` to anchor the date
2. Call `create_event` with the parsed details
3. Return a confirmation in plain English

### Schedule a meeting with a Google Meet link

```bash
curl -X POST http://localhost:4325/api/calendar/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "hassan",
    "message": "Schedule a 30-min call with haris@example.com tomorrow at 12pm, create a Meet link",
    "timezone": "Asia/Karachi"
  }'
```

When the user asks to "create a meet link" or "add video conference", Claude sets `add_meet_link: true` on `create_event` and a real Google Meet URL is attached to the event — identical to events created from the Google Calendar UI.

The response includes `meet_link` in the event data:
```json
{
  "meet_link": "https://meet.google.com/xxx-yyyy-zzz",
  "html_link": "https://www.google.com/calendar/event?eid=...",
  ...
}
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/calendar/schedule` | Natural language calendar action |
| `GET` | `/api/calendar/auth/start?user_id=` | Start OAuth flow for a user |
| `GET` | `/api/calendar/auth/callback` | OAuth callback (called by Google) |
| `GET` | `/api/calendar/auth/status?user_id=` | Check if user is authenticated |
| `DELETE` | `/api/calendar/auth/logout?user_id=` | Disconnect a user's calendar |
| `GET` | `/api/calendar/users` | List all connected users |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/mcp/sse` | MCP SSE endpoint (Claude Desktop) |

---

## Available Calendar Tools (Claude uses these internally)

| Tool | Description |
|---|---|
| `list_calendars` | List all user's calendars |
| `list_events` | List events with optional time filter |
| `search_events` | Full-text search across events |
| `get_event` | Fetch a single event by ID |
| `create_event` | Create a new event (pass `add_meet_link=true` to generate a Google Meet link) |
| `update_event` | Update an existing event |
| `delete_event` | Delete an event |
| `get_freebusy` | Check availability slots |
| `get_current_time` | Get current time in any timezone |
| `list_colors` | List available event colors |

---

## Claude Desktop Integration (MCP)

Add this to your Claude Desktop config:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "google-calendar": {
      "url": "http://localhost:4325/mcp/sse",
      "transport": "sse"
    }
  }
}
```

Restart Claude Desktop — the calendar tools will appear automatically.

---

## Testing with multiple users via ngrok

ngrok gives your local server a public HTTPS URL so multiple users can authorize from their own devices.

**1. Start ngrok:**
```bash
ngrok http 4325
# → https://abc123.ngrok-free.app
```

**2. Update Google Console:**

Go to **Clients** → edit your OAuth client → **Authorized redirect URIs** → add:
```
https://abc123.ngrok-free.app/api/calendar/auth/callback
```

**3. Update `.env`:**
```env
GOOGLE_REDIRECT_URI=https://abc123.ngrok-free.app/api/calendar/auth/callback
```

**4. Restart:**
```bash
make down && make up
```

**5. Share the auth URL with users:**
```
https://abc123.ngrok-free.app/api/calendar/auth/start?user_id=their-name
```

> **Note:** ngrok free tier generates a new URL each restart — update Google Console and `.env` each time.

---

## Token Storage

### Current (testing / development)

Tokens are stored as JSON files inside the Docker volume, one file per user:

```
/app/tokens/
  hassan.json
  ali.json
  sara.json
```

Each file contains the Google OAuth access token, refresh token, and expiry. Tokens auto-refresh before expiry — users only authorize once.

To inspect tokens:
```bash
docker compose exec calendar-mcp ls /app/tokens/
docker compose exec calendar-mcp cat /app/tokens/hassan.json
```

> **Important:** `make clean` removes the Docker volume and **wipes all tokens**. Users will need to re-authorize. Use `make down` to just stop the container without losing tokens.

### Production (recommended alternatives)

For a production multi-user system, replace the JSON file storage with:

| Option | When to use |
|---|---|
| **PostgreSQL** | Best for full user management with profiles, audit logs, etc. |
| **Redis** | Fast, great if you already have Redis in your stack |
| **AWS Secrets Manager / GCP Secret Manager** | Cloud-native, automatic rotation support |

Only `src/auth/token_manager.py` needs to change — swap `load_credentials`, `save_credentials`, and `delete_credentials` to read/write from your chosen store. Everything else stays the same.

---

## Going to Production

### Step 1 — Publish your Google app (removes test user restriction)

1. Google Console → **Audience** → click **"Publish App"** → confirm

After publishing, **any Google user** can authorize without being manually added.

### Step 2 — The unverified app warning

Until you complete Google's verification process, users will see:

```
⚠️ Google hasn't verified this app

[Back to safety]    Advanced ▼
                    → Continue to your-app (unsafe)
```

Users click **Advanced → Continue** to proceed. The app works fine — it just looks scary.

### Step 3 — Submit for Google verification (optional, removes the warning)

Required to remove the warning for public-facing apps:

1. Go to **Verification Center** in Google Console
2. Provide:
   - **Privacy Policy URL** — a public page explaining how you handle user data
   - **Homepage URL** — your app's landing page
   - **Authorized domain** — your production domain
3. Submit for review — Google takes **1–4 weeks**
4. After approval — clean consent screen, no warnings, any user can authorize

> For internal tools or small teams, skipping verification and using the "Continue" workaround is perfectly acceptable.

### Step 4 — Deploy the Docker container

The app is fully containerized. Deploy to any platform that supports Docker:

- **VPS** (DigitalOcean, Hetzner, Linode) — run `make up` on the server
- **AWS ECS / Google Cloud Run** — use the provided `Dockerfile`
- **Railway / Render** — connect your repo, set env vars, deploy

Set `GOOGLE_REDIRECT_URI` to your production domain:
```env
GOOGLE_REDIRECT_URI=https://yourdomain.com/api/calendar/auth/callback
```

Add the same URL to Google Console → Authorized redirect URIs.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-6` | Claude model to use |
| `GOOGLE_CLIENT_ID` | Yes | — | Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | Yes | — | Google OAuth Client Secret |
| `GOOGLE_REDIRECT_URI` | Yes | `http://localhost:4325/...` | Must match Google Console exactly |
| `GOOGLE_TOKENS_DIR` | No | `/app/tokens` | Directory for user token files |
| `GOOGLE_DEFAULT_CALENDAR` | No | `primary` | Default calendar ID |
| `APP_HOST` | No | `0.0.0.0` | Server host |
| `APP_PORT` | No | `4325` | Server port |
| `ENVIRONMENT` | No | `development` | `development` or `production` |

---

## Project Structure

```
google-calendar-mcp/
├── main.py                     # FastAPI app entry point
├── pyproject.toml              # Dependencies (UV)
├── Dockerfile                  # Multi-stage Docker build
├── docker-compose.yml          # Single service on port 4325
├── Makefile                    # Docker convenience commands
├── .env.example                # Environment variable template
└── src/
    ├── settings.py             # Pydantic settings
    ├── response.py             # Standardised JSON responses
    ├── schemas.py              # Request/response models
    ├── router.py               # FastAPI route definitions
    ├── auth/
    │   ├── oauth.py            # OAuth 2.0 flow (start, callback)
    │   └── token_manager.py    # Per-user token load/save/refresh
    ├── google/
    │   ├── client.py           # Google Calendar service factory
    │   └── tools.py            # 10 async calendar tool functions
    ├── nlp/
    │   └── service.py          # Claude tool-use agentic loop
    |   ___ router.py
    └── mcp_server/
        └── server.py           # FastMCP SSE server (10 tools)
```

---

## Local Development (without Docker)

```bash
# Install dependencies
make sync

# Run with auto-reload
make dev
```

For local runs, update `GOOGLE_TOKENS_DIR` in `.env`:
```env
GOOGLE_TOKENS_DIR=./tokens
```

Tokens will be saved to `claender-mcp/tokens/` on your machine.

---
