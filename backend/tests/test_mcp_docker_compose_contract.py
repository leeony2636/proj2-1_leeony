from pathlib import Path


COMPOSE_PATH = Path("docker-compose.yml")


def _compose_text() -> str:
    return COMPOSE_PATH.read_text(encoding="utf-8")


def test_compose_defines_api_mcp_and_database_services():
    text = _compose_text()

    assert "  api:\n" in text
    assert "  mcp:\n" in text
    assert "  db:\n" in text
    assert '["python", "-m", "mcp_server.server"]' in text
    assert 'EXPOSE 8000 8001' in Path("Dockerfile").read_text(encoding="utf-8")


def test_api_uses_internal_streamable_http_mcp_address():
    text = _compose_text()

    assert "MCP_CLIENT_TRANSPORT: streamable-http" in text
    assert "MCP_SERVER_URL: http://mcp:8001/mcp" in text
    assert "MCP_SERVER_TRANSPORT: streamable-http" in text
    assert "MCP_SERVER_HOST: 0.0.0.0" in text


def test_api_and_mcp_share_postgres_runtime():
    text = _compose_text()

    assert text.count("RUNTIME_REPOSITORY: postgres") == 2
    assert text.count("DATABASE_URL: postgresql://app:app@db:5432/app") == 2


def test_compose_waits_for_database_and_mcp_healthchecks():
    text = _compose_text()

    assert text.count("condition: service_healthy") == 3
    assert "pg_isready -U app -d app" in text
    assert "socket.create_connection(('127.0.0.1', 8001), 2).close()" in text


def test_docker_build_context_only_includes_runtime_sources():
    patterns = Path(".dockerignore").read_text(encoding="utf-8")

    assert "**\n" in patterns
    assert "!backend/**" in patterns
    assert "!mcp_server/**" in patterns
    assert "!skills/**" in patterns
    assert "!.env" not in patterns
