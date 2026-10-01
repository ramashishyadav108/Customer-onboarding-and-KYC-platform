"""Unit of work: one transaction exposing every repository (services never see sessions)."""

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from onboardx.repositories._errors import concurrent_update, is_unique_violation
from onboardx.repositories.assessment_repository import AssessmentRepository
from onboardx.repositories.audit_repository import AuditRepository
from onboardx.repositories.case_repository import CaseRepository
from onboardx.repositories.checklist_repository import ChecklistRepository
from onboardx.repositories.decision_repository import AccountRepository, DecisionRepository
from onboardx.repositories.document_repository import DocumentRepository
from onboardx.repositories.idempotency_repository import IdempotencyRepository
from onboardx.repositories.notification_repository import NotificationRepository
from onboardx.repositories.profile_repository import ProfileRepository
from onboardx.repositories.report_queries import ReportQueries
from onboardx.repositories.review_repository import ReviewRepository
from onboardx.repositories.rule_set_repository import RuleSetRepository
from onboardx.repositories.screening_repository import ScreeningRepository
from onboardx.repositories.state_history_repository import StateHistoryRepository
from onboardx.repositories.user_repository import UserRepository
from onboardx.repositories.watchlist_repository import WatchlistRepository


class UnitOfWork:
    """Context manager: commit explicitly; anything else (including errors) rolls back."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> Self:
        session = self._session_factory()
        self._session = session
        self.users = UserRepository(session)
        self.cases = CaseRepository(session)
        self.profiles = ProfileRepository(session)
        self.checklists = ChecklistRepository(session)
        self.state_history = StateHistoryRepository(session)
        self.audit = AuditRepository(session)
        self.rule_sets = RuleSetRepository(session)
        self.idempotency = IdempotencyRepository(session)
        self.documents = DocumentRepository(session)
        self.screenings = ScreeningRepository(session)
        self.assessments = AssessmentRepository(session)
        self.decisions = DecisionRepository(session)
        self.accounts = AccountRepository(session)
        self.notifications = NotificationRepository(session)
        self.review = ReviewRepository(session)
        self.watchlist = WatchlistRepository(session)
        self.reports = ReportQueries(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._session
        if session is None:
            return
        try:
            session.rollback()
        finally:
            session.close()
            self._session = None

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("unit of work is not active")
        try:
            self._session.commit()
        except OperationalError as error:
            raise concurrent_update() from error
        except IntegrityError as error:
            if is_unique_violation(error):
                raise concurrent_update() from error
            raise


UnitOfWorkFactory = Callable[[], UnitOfWork]


def make_uow_factory(session_factory: sessionmaker[Session]) -> UnitOfWorkFactory:
    def factory() -> UnitOfWork:
        return UnitOfWork(session_factory)

    return factory
