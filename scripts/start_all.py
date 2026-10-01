"""Single-command local run: start the backend (migrations + seed data) and the frontend dev server.

    python scripts/start_all.py [--backend-port 8000] [--frontend-port 3000] [--review-policy auto|manual]
        [--admin-signup approval|open]

Existing DATABASE_URL, JWT_SECRET and UPLOAD_DIR environment variables are respected; otherwise
synthetic dev defaults are used. Ctrl-C stops both processes.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
HEALTH_TIMEOUT_SECONDS = 60


def backend_python() -> str:
    for candidate in (BACKEND / ".venv" / "Scripts" / "python.exe", BACKEND / ".venv" / "bin" / "python"):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def wait_for_health(url: str, process: subprocess.Popen[bytes]) -> bool:
    deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310 - local URL
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    return False


def stop(processes: list[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="Start OnboardX backend and frontend")
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=3000)
    parser.add_argument(
        "--review-policy",
        choices=["auto", "manual"],
        default=os.environ.get("REVIEW_POLICY", "auto"),
        help="auto: clean LOW-risk cases are approved automatically (AC-07); manual: a compliance officer approves every case",
    )
    parser.add_argument(
        "--admin-signup",
        choices=["approval", "open"],
        default=os.environ.get("ADMIN_SIGNUP", "approval"),
        help="approval: admin sign-ups wait for an admin; open: anyone can sign up as admin (local demos only)",
    )
    args = parser.parse_args()

    npm = shutil.which("npm")
    if npm is None:
        print("npm was not found on PATH; install Node.js 18 or newer.", file=sys.stderr)
        return 1
    if not (FRONTEND / "node_modules").exists():
        print("Installing frontend dependencies (npm ci)...")
        subprocess.run([npm, "ci"], cwd=FRONTEND, check=True)

    backend_env = {
        **os.environ,
        "DATABASE_URL": os.environ.get("DATABASE_URL", "sqlite:///./onboardx.db"),
        "JWT_SECRET": os.environ.get("JWT_SECRET", "dev-only-not-a-secret-change-me-0123456789"),
        "UPLOAD_DIR": os.environ.get("UPLOAD_DIR", str(ROOT / "uploads")),
        "BACKEND_PORT": str(args.backend_port),
        "REVIEW_POLICY": args.review_policy,
        "ADMIN_SIGNUP": args.admin_signup,
    }
    backend_url = f"http://127.0.0.1:{args.backend_port}"
    processes: list[subprocess.Popen[bytes]] = []
    try:
        backend = subprocess.Popen([backend_python(), "scripts/run_backend.py"], cwd=BACKEND, env=backend_env)
        processes.append(backend)
        print(f"Starting backend on {backend_url} ...")
        if not wait_for_health(f"{backend_url}/health", backend):
            print("Backend did not become healthy; see its output above.", file=sys.stderr)
            return 1
        frontend_env = {**os.environ, "VITE_BACKEND_URL": backend_url}
        frontend = subprocess.Popen(
            [npm, "run", "start", "--", "--port", str(args.frontend_port), "--strictPort"],
            cwd=FRONTEND,
            env=frontend_env,
        )
        processes.append(frontend)
        print(f"\nOnboardX is starting: open http://localhost:{args.frontend_port}  (Ctrl-C to stop)")
        print("Staff logins: analyst1 / officer1 / admin1, password demo-<username>-pass (synthetic).")
        while all(process.poll() is None for process in processes):
            time.sleep(1)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        stop(processes)


if __name__ == "__main__":
    raise SystemExit(main())
