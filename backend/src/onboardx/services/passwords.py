"""PBKDF2-HMAC-SHA256 password hashing: ``pbkdf2_sha256$iterations$salt_hex$hash_hex``."""

import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 210_000
SALT_BYTES = 16


def hash_password(
    password: str, *, salt_hex: str | None = None, iterations: int = DEFAULT_ITERATIONS
) -> str:
    """Hash with a per-user random salt unless one is supplied (migrations precompute)."""
    salt = salt_hex or secrets.token_hex(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
    return f"{ALGORITHM}${iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time comparison; malformed stored values never verify."""
    try:
        algorithm, iterations, salt_hex, expected = stored.split("$")
        if algorithm != ALGORITHM:
            return False
        candidate = hash_password(password, salt_hex=salt_hex, iterations=int(iterations))
    except ValueError:
        return False
    return hmac.compare_digest(candidate.rsplit("$", 1)[1], expected)
