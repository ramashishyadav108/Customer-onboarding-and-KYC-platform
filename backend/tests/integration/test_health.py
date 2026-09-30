"""E1-S1 AC1: GET /health (F001, F002)."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_ac1_health_returns_ok(client: TestClient) -> None:
    """AC-01 (E1-S1 AC1 / F001): GET /health -> 200 with body exactly {"status":"ok"}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_listening(port: int, proc: "subprocess.Popen[bytes]", limit_s: float) -> float:
    """Return the monotonic time at which the server first accepts TCP connections."""
    deadline = time.monotonic() + limit_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise AssertionError("backend exited during startup")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return time.monotonic()
        except OSError:
            time.sleep(0.05)
    raise AssertionError("backend never started listening")


def test_nfr07_health_answers_within_one_second_of_successful_startup(tmp_path: Path) -> None:
    """NFR-07 / E1-S1 AC1 (F002): /health returns 200 within 1000 ms of a successful startup.

    NFR-07 times the endpoint from a *successful startup* (migrations applied, app built and
    the socket bound, which uvicorn does only after lifespan startup), not from interpreter
    spawn: on a cold Windows machine importing fastapi + sqlalchemy alone takes over a second.
    """
    port = _free_port()
    env = {
        **os.environ,
        "DATABASE_URL": "sqlite://",
        "JWT_SECRET": "test-secret-not-real",
        "BACKEND_PORT": str(port),
    }
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, str(BACKEND_DIR / "scripts" / "run_backend.py")],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ready_at = _wait_until_listening(port, proc, limit_s=30)
        response = httpx.get(f"http://127.0.0.1:{port}/health", timeout=2)
        elapsed_ms = (time.monotonic() - ready_at) * 1000
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    assert response.status_code == 200
    assert elapsed_ms <= 1000, f"first 200 arrived {elapsed_ms:.0f} ms after startup"


def test_ac1_health_is_public_and_unversioned(client: TestClient) -> None:
    """AC-01: /health needs no token and lives outside /api/v1."""
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 404


@pytest.mark.parametrize("path", ["/health"])
def test_ac1_health_has_no_extra_fields(client: TestClient, path: str) -> None:
    """AC-01: the body contains only status."""
    assert set(client.get(path).json()) == {"status"}
