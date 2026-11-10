from typing import Any

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def chat_body(content: str = "Hello there", model: str = "mock-1") -> dict[str, Any]:
    return {"model": model, "messages": [{"role": "user", "content": content}]}


def test_chat_requires_api_key() -> None:
    response = client.post("/v1/chat", json=chat_body())

    assert response.status_code == 401


def test_chat_returns_mock_reply(auth_headers: dict[str, str]) -> None:
    response = client.post("/v1/chat", json=chat_body(), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"].startswith("chat_")
    assert body["provider"] == "mock"
    assert body["model"] == "mock-1"
    assert body["content"] == "Mock reply to: Hello there"
    assert body["usage"] == {"input_tokens": 2, "output_tokens": 5}
    assert body["latency_ms"] >= 0


def test_unknown_model_returns_400(auth_headers: dict[str, str]) -> None:
    response = client.post("/v1/chat", json=chat_body(model="gpt-nonexistent"), headers=auth_headers)

    assert response.status_code == 400
    assert "mock-1" in response.json()["detail"]


def test_empty_messages_returns_422(auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/v1/chat", json={"model": "mock-1", "messages": []}, headers=auth_headers
    )

    assert response.status_code == 422


def test_provider_error_returns_502(auth_headers: dict[str, str]) -> None:
    response = client.post("/v1/chat", json=chat_body("[mock:error]"), headers=auth_headers)

    assert response.status_code == 502
    assert response.json() == {"detail": "Upstream provider error"}


def test_provider_timeout_returns_504(auth_headers: dict[str, str]) -> None:
    response = client.post("/v1/chat", json=chat_body("[mock:timeout]"), headers=auth_headers)

    assert response.status_code == 504
    assert response.json() == {"detail": "Upstream provider timed out"}


def test_falls_back_to_backup_provider(auth_headers: dict[str, str]) -> None:
    response = client.post("/v1/chat", json=chat_body("[mock:error@mock]"), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock-backup"
    assert body["content"] == "Mock reply to: [mock:error@mock]"