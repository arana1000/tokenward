from app.config import Settings


def test_password_is_hidden_when_settings_are_printed() -> None:
    settings = Settings(postgres_password="super-secret-value")

    assert "super-secret-value" not in repr(settings)
    assert "super-secret-value" not in str(settings)


def test_database_url_uses_psycopg_driver() -> None:
    settings = Settings(postgres_password="pw", postgres_host="db", postgres_port=5433)

    url = settings.database_url

    assert url.drivername == "postgresql+psycopg"
    assert url.host == "db"
    assert url.port == 5433


def test_sslmode_is_left_out_by_default() -> None:
    settings = Settings(postgres_password="pw", postgres_sslmode=None)

    assert settings.database_url.query == {}


def test_sslmode_is_added_when_set() -> None:
    settings = Settings(postgres_password="pw", postgres_sslmode="require")

    assert settings.database_url.query == {"sslmode": "require"}