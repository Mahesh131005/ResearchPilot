import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_liveness_probe(async_client: AsyncClient):
    """Test standard liveness probe returns healthy status."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_readiness_probe_healthy(async_client: AsyncClient):
    """Test readiness probe verifies database and operational dependencies."""
    response = await async_client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "checks" in data
    assert data["checks"]["database"] == "connected"
    assert data["checks"]["disk_storage"] == "writable"
    assert "billable_operations" in data["checks"]
    assert "provider_mode" in data["checks"]


@pytest.mark.asyncio
async def test_security_headers_present(async_client: AsyncClient):
    """Verify OWASP recommended security headers are attached by middleware."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("x-xss-protection") == "1; mode=block"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "geolocation=()" in response.headers.get("permissions-policy", "")


@pytest.mark.asyncio
async def test_request_body_size_limit(async_client: AsyncClient):
    """Verify requests declaring payload larger than 30MB receive HTTP 413."""
    # 35 MB in bytes = 35 * 1024 * 1024 = 36700160
    oversized_length = 35 * 1024 * 1024
    response = await async_client.post(
        "/api/v1/health",
        headers={"content-length": str(oversized_length)}
    )
    assert response.status_code == 413
    data = response.json()
    assert "exceeds maximum allowed size" in data.get("detail", "")


@pytest.mark.asyncio
async def test_chunked_request_body_size_limit(async_client: AsyncClient, monkeypatch):
    """Verify chunked streaming payloads exceeding MAX_REQUEST_BODY_SIZE_MB are rejected with 413."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "MAX_REQUEST_BODY_SIZE_MB", 1)

    async def streaming_body():
        chunk = b"X" * (512 * 1024)
        for _ in range(4):
            yield chunk

    response = await async_client.post(
        "/api/v1/auth/login",
        content=streaming_body(),
        headers={"transfer-encoding": "chunked"}
    )
    assert response.status_code == 413
    assert "exceeds maximum allowed size" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_system_metrics_json(async_client: AsyncClient):
    """Verify system telemetry metrics are exported in JSON format."""
    response = await async_client.get("/api/v1/system/metrics")
    assert response.status_code == 200
    assert response.headers.get("content-type") == "application/json"
    data = response.json()
    assert "uptime_seconds" in data
    assert "memory_rss_mb" in data
    assert "jobs" in data
    assert "active" in data["jobs"]
    assert "completed" in data["jobs"]
    assert "failed" in data["jobs"]
    assert "provider_telemetry" in data
    assert "input_tokens" in data["provider_telemetry"]
    assert "output_tokens" in data["provider_telemetry"]
    assert "total_tokens" in data["provider_telemetry"]
    assert "tavily_searches" in data["provider_telemetry"]


@pytest.mark.asyncio
async def test_system_metrics_prometheus(async_client: AsyncClient):
    """Verify system metrics can be exposed in standard Prometheus text format."""
    response = await async_client.get("/api/v1/system/metrics?format=prometheus")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    content = response.text
    assert "# HELP researchpilot_uptime_seconds" in content
    assert "# TYPE researchpilot_uptime_seconds gauge" in content
    assert "researchpilot_uptime_seconds" in content
    assert "researchpilot_memory_rss_megabytes" in content
    assert "researchpilot_jobs_total" in content
    assert "researchpilot_tokens_total" in content
    assert "researchpilot_web_searches_total" in content
