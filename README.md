# Tokenward

An LLM API gateway: one API in front of multiple LLM providers, with API keys,
rate limiting, retries, provider fallback and usage and cost tracking.
Work in progress.

## Status
- [x] FastAPI app with /health
- [x] PostgreSQL via Docker Compose
- [ ] Config, SQLAlchemy, Alembic
- [ ] API keys table and key authentication