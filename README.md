# User Management API

REST API for user management built with **FastAPI + SQLAlchemy 2.0 async + PostgreSQL**, deployed to **Google Cloud Run** with **Cloud SQL** and provisioned via **Cloud Build**.

Submission for the Advana Software Engineer Challenge.

---

## Highlights

- Clean architecture: `api → service → repository → model`, schemas as the wire boundary.
- Decoupled imports with barrel re-exports (every package exposes its public surface via `__init__.py`).
- Full CRUD with pagination, filtering, and search.
- JWT auth (access + refresh) with RBAC (`admin` / `user` / `guest`).
- Rate limiting (slowapi), security headers, CORS, request-id propagation.
- Structured logging (`structlog`) in JSON for Cloud Logging.
- Pytest + pytest-asyncio + httpx; unit tests (mocked) and integration tests (testcontainers + Alembic).
- Docker multi-stage, non-root user, healthcheck.
- Cloud Build pipeline: lint → test → build → push → migrate → deploy.

---

## Quickstart (local)

Requires Python 3.12 and Docker.

```bash
# 1) Boot Postgres
make docker-up

# 2) Install deps in a venv
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3) Configure env
cp .env.example .env

# 4) Run migrations
make migrate

# 5) Start the API
make dev
# -> http://localhost:8000/docs
```

Or fully containerized:

```bash
docker compose up --build
# -> http://localhost:8080/docs
```

---

## Project Layout

```
src/app/
├── api/          # HTTP layer (routers, deps, exception handlers)
│   └── v1/       # Versioned endpoints (auth, users)
├── services/     # Business logic
├── repositories/ # Persistence (async SQLAlchemy)
├── models/       # ORM models
├── schemas/      # Pydantic wire DTOs
├── core/         # Cross-cutting: config, logging, security, rate limit, middleware
├── db/           # Engine + session factory
├── factory.py    # FastAPI app factory
└── main.py       # ASGI entrypoint
migrations/       # Alembic
tests/
├── unit/         # Mocked, no DB
└── integration/  # testcontainers Postgres + real HTTP
```

Import direction is strictly one-way: `api → services → repositories → models`. Schemas and `core` are shared utilities. Models import nothing from the app.

---

## API Reference

OpenAPI docs at `/docs` (Swagger UI) and `/redoc`. The `Authorize` button in `/docs` works against `/v1/auth/login`.

### Auth

#### Self-register (public, always creates role=user)
```bash
curl -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jdoe",
    "email": "jdoe@example.com",
    "first_name": "Jane",
    "last_name": "Doe",
    "password": "StrongPass123!"
  }'
```

#### Login (OAuth2 password form)
```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=jdoe&password=StrongPass123!"
```
Response:
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 900
}
```

#### Refresh
```bash
curl -X POST http://localhost:8000/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "eyJhbGc..."}'
```

### Users

All endpoints below require `Authorization: Bearer <access_token>`.

#### Get current user
```bash
curl http://localhost:8000/v1/users/me -H "Authorization: Bearer $TOKEN"
```

#### Update current user
```bash
curl -X PATCH http://localhost:8000/v1/users/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"first_name": "Janet"}'
```

#### List users (admin only) — supports pagination + filters + search
```bash
curl "http://localhost:8000/v1/users?page=1&size=20&role=user&active=true&search=jane" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

#### Create user (admin only, arbitrary role)
```bash
curl -X POST http://localhost:8000/v1/users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "ops_admin",
    "email": "ops@example.com",
    "first_name": "Ops",
    "last_name": "Admin",
    "role": "admin",
    "active": true,
    "password": "StrongPass123!"
  }'
```

#### Read user by id (admin, or self)
```bash
curl http://localhost:8000/v1/users/$USER_ID -H "Authorization: Bearer $TOKEN"
```

#### Update user by id (admin, or self for own)
```bash
curl -X PATCH http://localhost:8000/v1/users/$USER_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"active": false, "role": "guest"}'
```

#### Delete user (admin only — soft delete, sets active=false)
```bash
curl -X DELETE http://localhost:8000/v1/users/$USER_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Health

```bash
curl http://localhost:8000/healthz
# {"status":"ok","db":"ok","version":"0.1.0"}
```

---

## Error Format

Every error returns a JSON body with a stable machine code and human message:
```json
{ "code": "conflict", "message": "User with this username or email already exists" }
```

Common codes: `validation_error` (422), `unauthorized` (401), `forbidden` (403), `not_found` (404), `conflict` (409), `rate_limited` (429), `internal_error` (500).

---

## Testing

```bash
# Full suite (needs Docker for testcontainers)
make test

# Unit only (no DB)
SKIP_INTEGRATION=1 pytest tests/unit -q

# With coverage
pytest --cov=src/app --cov-report=term-missing
```

- Unit tests use `AsyncMock` repositories. Fast and hermetic.
- Integration tests spin up a real Postgres via `testcontainers`, run Alembic migrations, then use SAVEPOINT rollback per test for isolation. Uses `httpx.AsyncClient` with `ASGITransport` (no network).

---

## Deploying to GCP

One-time setup:

```bash
PROJECT_ID=your-project
REGION=us-central1

# Enable APIs
gcloud services enable run.googleapis.com sqladmin.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com

# Artifact Registry repo
gcloud artifacts repositories create containers \
  --repository-format=docker --location=$REGION

# Cloud SQL Postgres 16
gcloud sql instances create se-challenge-pg \
  --database-version=POSTGRES_16 --tier=db-f1-micro --region=$REGION
gcloud sql databases create users_db --instance=se-challenge-pg
gcloud sql users create app --instance=se-challenge-pg --password='STRONG-PW'

# Secrets
echo -n 'postgresql+asyncpg://app:STRONG-PW@/users_db?host=/cloudsql/'$PROJECT_ID:$REGION:se-challenge-pg \
  | gcloud secrets create database-url --data-file=-
openssl rand -hex 32 | gcloud secrets create jwt-secret --data-file=-

# Runtime service account
gcloud iam service-accounts create run-sa
SA="run-sa@$PROJECT_ID.iam.gserviceaccount.com"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA" --role=roles/cloudsql.client
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor
```

Trigger a build:
```bash
gcloud builds submit --config=cloudbuild.yaml
```

The pipeline lints, tests, builds the image, pushes it, runs Alembic migrations as a Cloud Run Job, then deploys the service.

---

## Architecture Notes

- **Cloud SQL connectivity:** uses the unix socket mounted by Cloud Run (`--add-cloudsql-instances`) via the asyncpg query param `?host=/cloudsql/PROJECT:REGION:INSTANCE`. No sidecar, no extra port.
- **Connection pool sizing:** `pool_size=5`, `max_overflow=5` per Cloud Run instance × `max-instances=10` ⇒ ≤ 100 concurrent DB connections, fits the small Cloud SQL tier limit.
- **`pool_pre_ping=True`** + **`pool_recycle=1800`** prevents stale-connection `InterfaceError` after Cloud SQL idles a socket.
- **Engine lifecycle:** created at import time, disposed in the FastAPI `lifespan` shutdown. `tini` forwards SIGTERM cleanly.
- **Migrations run as a separate Cloud Run Job** before service rollout — never on app boot — to avoid races between scaled-out instances.
- **Refresh tokens** are stateless. Production would add a Redis denylist on `jti`; out of scope for this challenge.

---

## Security Checklist

- Passwords hashed with bcrypt (cost 12).
- JWT signed with HS256, secret in Secret Manager.
- SQL access only through SQLAlchemy parameterized queries.
- Pydantic `SecretStr` for password fields (never logged).
- structlog processor redacts `password|authorization|token|jwt_secret` keys.
- Security response headers always on (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`; HSTS in prod).
- CORS strictly bound to configured origins; `*` rejected when credentials enabled.
- Rate limits: 60/min default, 5/min on `/auth/login` against brute force.
- Constant-ish authentication time (`verify_password` runs even on missing user).
- Soft delete (deactivation) preserves audit history.

---

## License

MIT
