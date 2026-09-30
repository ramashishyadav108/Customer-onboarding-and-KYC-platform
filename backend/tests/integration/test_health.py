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


def test_ac1_health_answers_within_one_second_of_process_start(tmp_path: Path) -> None:
    """AC-01 (E1-S1 AC1 / F002): first 200 arrives within 1000 ms of spawning run_backend.py."""
    port = _free_port()
    env = {
        **os.environ,
        "DATABASE_URL": "sqlite://",
        "JWT_SECRET": "test-secret-not-real",
        "BACKEND_PORT": str(port),
    }
    started = time.monotonic()
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, str(BACKEND_DIR / "scripts" / "run_backend.py")],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    elapsed_ms = -1.0
    try:
        while time.monotonic() - started < 5:
            try:
                response = httpx.get(f"http://127.0.0.1:{port}/health", timeout=0.5)
            except httpx.TransportError:
                time.sleep(0.05)
                continue
            if response.status_code == 200:
                elapsed_ms = (time.monotonic() - started) * 1000
                break
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    assert elapsed_ms >= 0, "health never answered"
    assert elapsed_ms <= 1000, f"first 200 after {elapsed_ms:.0f} ms"


def test_ac1_health_is_public_and_unversioned(client: TestClient) -> None:
    """AC-01: /health needs no token and lives outside /api/v1."""
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 404


@pytest.mark.parametrize("path", ["/health"])
def test_ac1_health_has_no_extra_fields(client: TestClient, path: str) -> None:
    """AC-01: the body contains only status."""
    assert set(client.get(path).json()) == {"status"}
