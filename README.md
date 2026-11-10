# Tokenward

An LLM API gateway: one API in front of multiple LLM providers, with API keys,
rate limiting, retries, provider fallback and usage and cost tracking.
Work in progress.

## Status
- [x] FastAPI app with /health
- [x] PostgreSQL via Docker Compose
- [x] Settings from .env, SQLAlchemy connection, /ready endpoint
- [x] Alembic migrations and api_keys table
- [x] API key generation, revocation CLI and Bearer authentication
- [x] Provider interface, mock provider and POST /v1/chat
- [x] Request logging (latency, tokens, cost, outcome)
- [x] Retries with exponential backoff and provider fallback
- [ ] Per-key rate limiting
- [ ] CI, Docker image and first deploy