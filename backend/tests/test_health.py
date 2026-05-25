from uuid import UUID

from fastapi.testclient import TestClient

from app.db.session import get_db_session
from app.main import app, create_app


class ReadySession:
    async def execute(self, statement: object) -> None:
        self.statement = statement


class UnavailableSession:
    async def execute(self, statement: object) -> None:
        raise RuntimeError("database is unavailable")


def test_health_check() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "easy-mes"}
    request_id = response.headers["X-Request-Id"]
    assert UUID(request_id)
    assert response.headers["X-Trace-Id"] == request_id


def test_request_id_header_is_propagated() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health", headers={"X-Request-Id": "shop-floor-terminal-42"})

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "shop-floor-terminal-42"
    assert response.headers["X-Trace-Id"] == "shop-floor-terminal-42"


def test_trace_id_header_is_propagated() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/health",
            headers={"X-Request-Id": "shop-floor-terminal-42", "X-Trace-Id": "trace-line-a"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "shop-floor-terminal-42"
    assert response.headers["X-Trace-Id"] == "trace-line-a"


def test_cors_preflight_includes_request_headers() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/health",
            headers={"Origin": "http://127.0.0.1:5180", "Access-Control-Request-Method": "GET"},
        )

    assert response.status_code == 200
    assert UUID(response.headers["X-Request-Id"])
    assert response.headers["X-Trace-Id"] == response.headers["X-Request-Id"]


def test_readiness_check_returns_ready_when_database_ping_succeeds() -> None:
    session = ReadySession()

    async def override_db_session():
        yield session

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/health/ready")
    finally:
        del app.dependency_overrides[get_db_session]

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "easy-mes", "checks": {"database": "ok"}}


def test_readiness_check_returns_unavailable_when_database_ping_fails() -> None:
    async def override_db_session():
        yield UnavailableSession()

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/health/ready")
    finally:
        del app.dependency_overrides[get_db_session]

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "service": "easy-mes",
        "checks": {"database": "unavailable"},
    }


def test_app_lifespan_disposes_database_engine(monkeypatch) -> None:
    disposed = False

    async def fake_dispose_engine() -> None:
        nonlocal disposed
        disposed = True

    monkeypatch.setattr("app.main.dispose_engine", fake_dispose_engine)
    test_app = create_app()

    with TestClient(test_app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert disposed
