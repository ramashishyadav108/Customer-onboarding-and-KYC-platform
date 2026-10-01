"""Ports (Protocols) that outer layers implement; the domain never performs I/O itself."""

from datetime import datetime
from typing import Any, Protocol

from onboardx.domain.enums import CaseState


class Clock(Protocol):
    def now(self) -> datetime:
        """Current time as an aware UTC datetime."""
        ...


class NotificationSender(Protocol):
    def send(self, case_id: str, event: str, text: str) -> None: ...


class FileStore(Protocol):
    def save(self, relative_path: str, content: bytes) -> None: ...

    def read(self, relative_path: str) -> bytes: ...

    def delete(self, relative_path: str) -> None: ...


class TransitionObserver(Protocol):
    def on_transition(
        self, case_id: str, from_state: CaseState | None, to_state: CaseState
    ) -> None:
        """Called inside the transition transaction after the history row is appended."""
        ...


class TransitionRecorder(Protocol):
    """Transactional sibling of TransitionObserver: receives the open unit of work (opaque to
    the domain) so the record commits or rolls back with the transition (AC-09.1)."""

    def record_transition(
        self, uow: Any, case_id: str, from_state: CaseState | None, to_state: CaseState
    ) -> None: ...
