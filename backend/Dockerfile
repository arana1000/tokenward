FROM python:3.14-slim

# Don't write .pyc files, and send log output straight to the terminal.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first. This layer is cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then copy the application code, which changes far more often.
COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app

# Run as an unprivileged user, not root.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Apply any pending migrations, then start the server.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]