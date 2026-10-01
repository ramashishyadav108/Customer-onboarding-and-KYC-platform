"""Login and HS256 JWT issue/verify (E1-S2). Role enforcement lives in controllers (NFR-04)."""

from dataclasses import dataclass
from functools import cache

import jwt

from onboardx.domain.enums import Role
from onboardx.domain.errors import AuthenticationError
from onboardx.domain.ports import Clock
from onboardx.repositories.unit_of_work import UnitOfWorkFactory
from onboardx.services.passwords import hash_password, verify_password

ALGORITHM = "HS256"
DEFAULT_TTL_SECONDS = 1800


@cache
def _dummy_hash() -> str:
    """Stored hash verified for unknown users so timing does not reveal the username."""
    return hash_password("not-a-real-password", salt_hex="00" * 16)


@dataclass(frozen=True)
class TokenClaims:
    subject: str
    role: Role
    case_id: str | None
    expires_at: int


@dataclass(frozen=True)
class IssuedToken:
    access_token: str
    expires_in: int


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    role: Role
    expires_in: int
    case_id: str | None


class AuthService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        secret: str,
        clock: Clock,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._uow_factory = uow_factory
        self._secret = secret
        self._clock = clock
        self._ttl = ttl_seconds

    def login(self, username: str, password: str) -> LoginResult:
        """Same error for unknown user and wrong password; never says which was wrong."""
        with self._uow_factory() as uow:
            user = uow.users.get_by_username(username)
        stored = user.password_hash if user is not None else _dummy_hash()
        valid = verify_password(password, stored)
        if user is None or not valid:
            raise AuthenticationError("Invalid credentials")
        issued = self.issue_token(user.username, user.role, user.case_id)
        return LoginResult(issued.access_token, user.role, issued.expires_in, user.case_id)

    def issue_token(self, subject: str, role: Role, case_id: str | None = None) -> IssuedToken:
        expires_at = int(self._clock.now().timestamp()) + self._ttl
        claims: dict[str, object] = {"sub": subject, "role": str(role), "exp": expires_at}
        if case_id is not None:
            claims["case_id"] = case_id
        token = jwt.encode(claims, self._secret, algorithm=ALGORITHM)
        return IssuedToken(token, self._ttl)

    def verify_token(self, token: str) -> TokenClaims:
        """Decode and validate; expiry is judged against the injected clock."""
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],
                options={"verify_exp": False, "require": ["exp", "sub", "role"]},
            )
            role = Role(claims["role"])
            expires_at = int(claims["exp"])
        except (jwt.InvalidTokenError, ValueError, TypeError) as error:
            raise AuthenticationError("Invalid token") from error
        if expires_at <= int(self._clock.now().timestamp()):
            raise AuthenticationError("Token expired")
        case_id = claims.get("case_id")
        return TokenClaims(
            str(claims["sub"]), role, None if case_id is None else str(case_id), expires_at
        )
