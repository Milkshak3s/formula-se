from app.core.config import Settings


def _url(v: str) -> str:
    return Settings(database_url=v).database_url


def test_bare_postgresql_gets_psycopg_driver():
    # CloudNativePG-style URI (no driver) must be routed to psycopg3.
    assert (
        _url("postgresql://formulase:pw@formula-se-db-rw:5432/formulase")
        == "postgresql+psycopg://formulase:pw@formula-se-db-rw:5432/formulase"
    )


def test_postgres_scheme_alias_normalized():
    assert _url("postgres://u:p@host/db") == "postgresql+psycopg://u:p@host/db"


def test_explicit_driver_left_untouched():
    v = "postgresql+psycopg://u:p@host:5432/db"
    assert _url(v) == v
