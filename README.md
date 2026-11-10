# Tokenward

[![CI](https://github.com/arana1000/tokenward/actions/workflows/ci.yml/badge.svg)](https://github.com/arana1000/tokenward/actions/workflows/ci.yml)

An LLM API gateway: one API in front of multiple LLM providers, with API keys,
rate limiting, retries, provider fallback and usage and cost tracking.
Work in progress.

## Run it with Docker

Requires Docker. Copy `.env.example` to `.env`, set a password, then:

    docker compose up -d --build

The API is at http://127.0.0.1:8000 and interactive docs at http://127.0.0.1:8000/docs.

Create an API key:

    docker compose exec api python -m app.cli create-key --name "my key"

## Status
- [x] FastAPI app with /health
- [x] PostgreSQL via Docker Compose
- [x] Settings from .env, SQLAlchemy connection, /ready endpoint
- [x] Alembic migrations and api_keys table
- [x] API key generation, revocation CLI and Bearer authentication
- [x] Provider interface, mock provider and POST /v1/chat
- [x] Request logging (latency, tokens, cost, outcome)
- [x] Retries with exponential backoff and provider fallback
- [x] Per-key rate limiting (token bucket, 429 with Retry-After)
- [x] CI with GitHub Actions and a Docker image for the API
- [ ] First deploy

## Known limitations
- Rate limiting is held in memory, so limits reset when the app restarts and are
  not shared between instances. Running several instances would need a shared
  store such as Redis.
- Endpoints are synchronous, so concurrent requests are capped by the worker
  thread pool.