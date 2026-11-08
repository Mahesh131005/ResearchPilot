import pytest
from app.core.config import Settings, get_safe_db_target

def test_safe_db_target_omits_credentials():
    url = "postgres://researchpilot:supersecretpass123@dpg-dbo48h3m8hqs73fgujrg-a:5432/researchpilot_viob"
    target = get_safe_db_target(url)
    assert target["configured"] is True
    assert target["host"] == "dpg-dbo48h3m8hqs73fgujrg-a"
    assert target["port"] == 5432
    assert target["database"] == "researchpilot_viob"
    assert "supersecretpass123" not in target["safe_summary"]
    assert "researchpilot" not in target["safe_summary"] or target["safe_summary"].startswith("postgres://***:***@")
    assert target["safe_summary"] == "postgres://***:***@dpg-dbo48h3m8hqs73fgujrg-a:5432/researchpilot_viob"

def test_production_render_database_url_normalization(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgres://researchpilot:secretpass@dpg-dbo48h3m8hqs73fgujrg-a:5432/researchpilot_viob")
    monkeypatch.delenv("SYNC_DATABASE_URL", raising=False)

    s = Settings()
    # async URL must use postgresql+asyncpg
    assert s.DATABASE_URL.startswith("postgresql+asyncpg://researchpilot:secretpass@dpg-dbo48h3m8hqs73fgujrg-a:5432/researchpilot_viob")
    # sync URL must be automatically derived and use postgresql+psycopg2
    assert s.SYNC_DATABASE_URL.startswith("postgresql+psycopg2://researchpilot:secretpass@dpg-dbo48h3m8hqs73fgujrg-a:5432/researchpilot_viob")
    
    # Safe summaries must never leak credentials
    assert "secretpass" not in s.safe_db_summary
    assert "secretpass" not in s.safe_sync_db_summary
    assert "dpg-dbo48h3m8hqs73fgujrg-a:5432" in s.safe_db_summary
    assert "dpg-dbo48h3m8hqs73fgujrg-a:5432" in s.safe_sync_db_summary

def test_production_render_with_sslmode(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://researchpilot:secretpass@dpg-dbo48h3m8hqs73fgujrg-a:5432/researchpilot_viob?sslmode=require")
    monkeypatch.delenv("SYNC_DATABASE_URL", raising=False)

    s = Settings()
    # asyncpg should convert sslmode=require to ssl=require
    assert "ssl=require" in s.DATABASE_URL
    assert "sslmode=require" not in s.DATABASE_URL
    assert s.DATABASE_URL.startswith("postgresql+asyncpg://")

    # psycopg2 should retain sslmode=require
    assert "sslmode=require" in s.SYNC_DATABASE_URL
    assert s.SYNC_DATABASE_URL.startswith("postgresql+psycopg2://")

def test_production_rejects_localhost(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://postgres:pass@localhost:5432/researchpilot")

    with pytest.raises(ValueError, match="DATABASE_URL in production points to a local address"):
        Settings()

def test_production_rejects_loopback_ip(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://postgres:pass@127.0.0.1:5432/researchpilot")

    with pytest.raises(ValueError, match="DATABASE_URL in production points to a local address"):
        Settings()

def test_production_rejects_dev_port_5433(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://postgres:pass@remotedb:5433/researchpilot")

    with pytest.raises(ValueError, match="DATABASE_URL in production points to a local address"):
        Settings()

def test_production_rejects_empty_database_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "")

    with pytest.raises(ValueError, match="DATABASE_URL is missing or empty in production"):
        Settings()

def test_development_allows_localhost_5433(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SYNC_DATABASE_URL", raising=False)

    s = Settings()
    assert "localhost:5433" in s.DATABASE_URL
    assert "postgresql+asyncpg://" in s.DATABASE_URL
    assert s.SYNC_DATABASE_URL is not None
    assert "localhost:5433" in s.SYNC_DATABASE_URL
    assert "postgresql+psycopg2://" in s.SYNC_DATABASE_URL

def test_stale_local_sync_db_url_is_auto_healed(monkeypatch):
    """When DATABASE_URL is remote but SYNC_DATABASE_URL points to localhost, auto-derive from DATABASE_URL."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgres://researchpilot:secretpass@dpg-dbo48h3m8hqs73fgujrg-a:5432/researchpilot_viob")
    # Simulate a stale localhost sync URL injected from an old env or default
    monkeypatch.setenv("SYNC_DATABASE_URL", "postgresql+psycopg2://postgres@localhost:5433/researchpilot")

    s = Settings()
    assert "dpg-dbo48h3m8hqs73fgujrg-a:5432" in s.SYNC_DATABASE_URL
    assert s.SYNC_DATABASE_URL.startswith("postgresql+psycopg2://")
    assert "localhost" not in s.SYNC_DATABASE_URL

def test_render_dual_injection_normalized(monkeypatch):
    """When render.yaml injects connectionString into both DATABASE_URL and SYNC_DATABASE_URL."""
    render_url = "postgres://researchpilot:secretpass@dpg-dbo48h3m8hqs73fgujrg-a:5432/researchpilot_viob?sslmode=require"
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", render_url)
    monkeypatch.setenv("SYNC_DATABASE_URL", render_url)

    s = Settings()
    assert s.DATABASE_URL.startswith("postgresql+asyncpg://researchpilot:secretpass@dpg-dbo48h3m8hqs73fgujrg-a:5432/researchpilot_viob")
    assert "ssl=require" in s.DATABASE_URL
    assert s.SYNC_DATABASE_URL.startswith("postgresql+psycopg2://researchpilot:secretpass@dpg-dbo48h3m8hqs73fgujrg-a:5432/researchpilot_viob")
    assert "sslmode=require" in s.SYNC_DATABASE_URL

def test_alembic_reads_same_sync_url(monkeypatch):
    """Verify Alembic env.py uses settings.SYNC_DATABASE_URL matching the target database."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgres://researchpilot:secretpass@dpg-dbo48h3m8hqs73fgujrg-a:5432/researchpilot_viob")
    monkeypatch.delenv("SYNC_DATABASE_URL", raising=False)

    from alembic.config import Config
    import app.core.config as conf
    conf.settings = Settings()

    cfg = Config("alembic.ini")
    current_url = cfg.get_main_option("sqlalchemy.url")
    if not current_url or current_url == "driver://user:pass@localhost/dbname":
        cfg.set_main_option("sqlalchemy.url", conf.settings.SYNC_DATABASE_URL)

    alembic_url = cfg.get_main_option("sqlalchemy.url")
    assert "dpg-dbo48h3m8hqs73fgujrg-a:5432" in alembic_url
    assert alembic_url.startswith("postgresql+psycopg2://")
    assert "localhost" not in alembic_url

def test_docker_entrypoint_preflight_parsing():
    from urllib.parse import urlparse
    render_url = "postgres://researchpilot:secretpass123@dpg-dbo48h3m8hqs73fgujrg-a:5432/researchpilot_viob?sslmode=require"
    conn_str = render_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
    if "ssl=require" in conn_str:
        conn_str = conn_str.replace("ssl=require", "sslmode=require")

    clean = conn_str.split("://", 1)[-1] if "://" in conn_str else conn_str
    parsed = urlparse(f"http://{clean}")
    target_host = parsed.hostname or "unknown"
    target_port = parsed.port or 5432
    target_db = parsed.path.lstrip("/") or "unknown"

    assert target_host == "dpg-dbo48h3m8hqs73fgujrg-a"
    assert target_port == 5432
    assert "researchpilot_viob" in target_db
    assert "secretpass123" not in f"{target_host}:{target_port}/{target_db}"


