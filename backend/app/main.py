from fastapi import FastAPI

app = FastAPI(title="Tokenward API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check: confirms the API process is running and answering requests."""
    return {"status": "ok"}