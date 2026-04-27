# Insighta Labs+ — Backend

A secure, multi-interface profile intelligence platform built with FastAPI. This is the backend service powering both the CLI and web portal.

## System Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   insighta-cli  │     │  insighta-web   │
│  (local tool)   │     │ (web portal)    │
└────────┬────────┘     └────────┬────────┘
         │ Bearer token           │ HTTP-only cookie
         │ X-API-Version: 1       │ X-API-Version: 1
         └──────────┬─────────────┘
                    ▼
         ┌──────────────────┐
         │  insighta-backend │
         │   (FastAPI)       │
         │                   │
         │  /auth/*          │
         │  /api/profiles    │
         └──────────┬────────┘
                    │
         ┌──────────▼────────┐
         │     SQLite DB      │
         │  profiles          │
         │  users             │
         │  refresh_tokens    │
         └───────────────────┘
```

The backend is the single source of truth. Both interfaces share the same API, the same database, and the same authentication system. The CLI communicates via Bearer tokens in headers. The web portal communicates via HTTP-only cookies. The backend accepts both transparently.

## Authentication Flow

### CLI Flow (PKCE)

```
1. CLI generates:
   - state         → random string for CSRF protection
   - code_verifier → random secret, never sent to GitHub
   - code_challenge → base64url(sha256(code_verifier))

2. CLI opens browser with GitHub OAuth URL:
   https://github.com/login/oauth/authorize
     ?client_id=...
     &code_challenge=...
     &code_challenge_method=S256
     &state=...
     &redirect_uri=http://localhost:8765/callback

3. User authenticates on GitHub

4. GitHub redirects to http://localhost:8765/callback?code=...&state=...

5. CLI validates state matches, then sends to backend:
   GET /auth/github/callback?code=...&state=...&code_verifier=...&client_source=cli

6. Backend:
   - Exchanges code + code_verifier with GitHub
   - Fetches user info from GitHub API
   - Creates or updates user in DB
   - Issues access token (3 min) + refresh token (5 min)
   - Returns both tokens + username

7. CLI stores tokens at ~/.insighta/credentials.json
```

### Web Flow

```
1. User clicks "Continue with GitHub" on login page
2. Portal redirects to /auth/github on backend
3. Backend generates state, stores in session, redirects to GitHub
4. GitHub redirects to /auth/github/callback on backend
5. Backend validates state, exchanges code with GitHub
6. Backend sets access_token and refresh_token as HTTP-only cookies
7. User is redirected to /dashboard
```

### Why Two OAuth Apps?

GitHub OAuth apps support one callback URL. The CLI uses a random local port (`http://localhost:8765/callback`) while the web portal uses the deployed URL. Two separate GitHub OAuth apps are registered — one per interface — each with its own `client_id` and `client_secret`. The backend selects the correct credentials based on the `client_source` parameter in the callback.

## Token Handling

| Token | Expiry | Storage |
|---|---|---|
| Access token | 3 minutes | CLI: credentials.json / Web: HTTP-only cookie |
| Refresh token | 5 minutes | DB (hashed with sha256) |

Access tokens are JWTs signed with HS256. The payload carries `sub` (user ID), `role`, and `exp`.

Refresh tokens are random strings. Only the `sha256` hash is stored in the database — the raw token is returned to the client once and never stored in plaintext.

**Rotation:** Every use of a refresh token immediately invalidates it and issues a new pair. A used or expired refresh token returns 401. This means if a refresh token is stolen, using it invalidates the legitimate user's token too — signalling a breach.

## Role Enforcement

Two roles: `admin` and `analyst`. Default on signup: `analyst`.

| Role | Permissions |
|---|---|
| admin | Create profiles, delete profiles, read, search, export |
| analyst | Read, search, export only |

Enforcement is implemented via FastAPI dependency injection — not scattered if-statements:

```python
# Any authenticated user
read_router = APIRouter(dependencies=[Depends(get_current_user)])

# Admin only
admin_router = APIRouter(dependencies=[Depends(require_admin)])
```

`get_current_user` validates the JWT from either the `Authorization: Bearer` header (CLI) or the `access_token` cookie (web). `require_admin` wraps `get_current_user` and checks `user.role == "admin"`.

Inactive users (`is_active=False`) receive 403 on all requests regardless of role.

## Natural Language Parsing

The `GET /api/profiles/search?q=` endpoint uses rule-based parsing — no LLMs or NLP libraries.

Queries are normalized (lowercased, unicode-stripped) and tokenized by whitespace. Tokens are matched against lookup tables:

- **Gender:** `male`, `males`, `man`, `men`, `female`, `females`, `woman`, `women`
- **Age groups:** `child`, `teenager`, `adult`, `senior` (and plurals)
- **Special age signals:** `young` → ages 16–24
- **Range signals:** `above`/`over`/`older` + number → `min_age`; `below`/`under`/`younger` + number → `max_age`
- **Countries:** 63 countries matched by full name. Multi-word countries (e.g. "south africa") matched as bigrams

If both genders appear in a query, neither is applied as a filter. If no recognisable signals are found, the endpoint returns 422.

Examples:

| Query | Interpreted as |
|---|---|
| `young males from nigeria` | gender=male, min_age=16, max_age=24, country_id=NG |
| `females above 30` | gender=female, min_age=30 |
| `adult males from south africa` | gender=male, age_group=adult, country_id=ZA |

## API Reference

All `/api/*` endpoints require:
- `Authorization: Bearer <token>` header OR `access_token` cookie
- `X-API-Version: 1` header

### Auth Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/auth/github` | Redirect to GitHub OAuth |
| GET | `/auth/github/callback` | Handle OAuth callback, issue tokens |
| POST | `/auth/refresh` | Rotate refresh token, issue new pair |
| POST | `/auth/logout` | Invalidate refresh token |
| GET | `/auth/me` | Get current user info |

### Profile Endpoints

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/api/profiles` | analyst+ | List with filters, sorting, pagination |
| GET | `/api/profiles/search` | analyst+ | Natural language search |
| GET | `/api/profiles/{id}` | analyst+ | Single profile |
| GET | `/api/profiles/export` | analyst+ | Export as CSV |
| POST | `/api/profiles` | admin | Create profile |
| DELETE | `/api/profiles/{id}` | admin | Delete profile |

### Pagination Shape

```json
{
  "status": "success",
  "page": 1,
  "limit": 10,
  "total": 2026,
  "total_pages": 203,
  "links": {
    "self": "/api/profiles?page=1&limit=10",
    "next": "/api/profiles?page=2&limit=10",
    "prev": null
  },
  "data": [...]
}
```

## Rate Limiting

| Scope | Limit |
|---|---|
| `/auth/*` | 10 requests / minute |
| All other endpoints | 60 requests / minute per IP |

Returns `429 Too Many Requests` when exceeded. Implemented as an in-memory sliding window middleware — suitable for single-instance deployments.

## Logging

Every request logs: method, path, status code, response time.

```
INFO GET /api/profiles 200 0.034s
INFO POST /auth/refresh 200 0.012s
```

## Local Setup

**Requirements:** Python 3.12+, [uv](https://github.com/astral-sh/uv)

```bash
git clone https://github.com/HNG-Backend-Tasks/insighta-backend
cd insighta-backend
uv sync
```

Create `.env`:
```env
DATABASE_URL=sqlite:///./insighta.db
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
GITHUB_CLIENT_ID_WEB=your_web_client_id
GITHUB_CLIENT_SECRET_WEB=your_web_client_secret
GITHUB_CLIENT_ID_CLI=your_cli_client_id
GITHUB_CLIENT_SECRET_CLI=your_cli_client_secret
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
```

Seed the database:
```bash
uv run python -m app.seed
```

Run the server:
```bash
uv run uvicorn app.main:app --reload
```

## Running Tests

```bash
uv run pytest tests/ -v
```

## Docker

```bash
docker compose up --build
```

## Project Structure

```
app/
├── auth/
│   ├── dependencies.py   ← get_current_user, require_admin
│   ├── router.py         ← auth endpoints
│   ├── schemas.py        ← request/response models
│   └── service.py        ← token logic, GitHub exchange, user upsert
├── api.py                ← profile endpoints
├── config.py             ← settings from .env
├── database.py           ← SQLAlchemy engine and session
├── main.py               ← FastAPI app, middleware, exception handlers
├── models.py             ← SQLAlchemy + Pydantic models
├── parser.py             ← natural language query parser
├── seed.py               ← database seeding
├── service.py            ← profile business logic
└── utils.py              ← utcnow() helper
tests/
├── conftest.py           ← test DB, fixtures, client setup
├── test_api.py           ← HTTP-level API tests
├── test_auth.py          ← auth flow tests
├── test_parser.py        ← NLP parser tests
└── test_profiles.py      ← service-level profile tests
```