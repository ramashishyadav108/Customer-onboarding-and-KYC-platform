"""Ports (Protocols) that outer layers implement; the domain never performs I/O itself."""

from datetime import datetime
from typing import Protocol

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


class TransitionObserver(Protocol):
    def on_transition(
        self, case_id: str, from_state: CaseState | None, to_state: CaseState
    ) -> None:
        """Called inside the transition transaction after the history row is appended."""
        ...
