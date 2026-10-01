"""Append-only analyst queries, prospect responses and closures (AC-13, NFR-02)."""

from collections import defaultdict

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from onboardx.domain.views import QueryResponseView, QueryView
from onboardx.repositories.models.queries import (
    CaseQueryModel,
    QueryClosureModel,
    QueryResponseModel,
)


def derive_status(closed: bool, responded: bool) -> str:
    """OPEN until the prospect answers, ANSWERED after, CLOSED once the analyst closes it."""
    if closed:
        return "CLOSED"
    return "ANSWERED" if responded else "OPEN"


class QueryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_query(
        self, *, query_id: str, case_id: str, raised_by: str, message: str, created_at: str
    ) -> None:
        self._session.add(
            CaseQueryModel(
                query_id=query_id,
                case_id=case_id,
                raised_by=raised_by,
                message=message,
                created_at=created_at,
            )
        )
        self._session.flush()

    def add_response(
        self,
        *,
        response_id: str,
        query_id: str,
        case_id: str,
        author: str,
        message: str,
        created_at: str,
    ) -> None:
        self._session.add(
            QueryResponseModel(
                response_id=response_id,
                query_id=query_id,
                case_id=case_id,
                author=author,
                message=message,
                created_at=created_at,
            )
        )
        self._session.flush()

    def add_closure(self, *, query_id: str, closed_by: str, created_at: str) -> None:
        self._session.add(
            QueryClosureModel(query_id=query_id, closed_by=closed_by, created_at=created_at)
        )
        self._session.flush()

    def get_view(self, case_id: str, query_id: str) -> QueryView | None:
        return next((v for v in self.list_views(case_id) if v.query_id == query_id), None)

    def list_views(self, case_id: str) -> list[QueryView]:
        """Queries of a case oldest first, each with its responses and derived status."""
        queries = self._session.scalars(
            select(CaseQueryModel)
            .where(CaseQueryModel.case_id == case_id)
            .order_by(text("case_queries.rowid"))
        ).all()
        ids = [q.query_id for q in queries]
        responses = self._responses(ids)
        closed = set(
            self._session.scalars(
                select(QueryClosureModel.query_id).where(QueryClosureModel.query_id.in_(ids))
            )
        )
        return [
            QueryView(
                q.query_id,
                q.case_id,
                q.raised_by,
                q.message,
                derive_status(q.query_id in closed, bool(responses[q.query_id])),
                q.created_at,
                tuple(responses[q.query_id]),
            )
            for q in queries
        ]

    def _responses(self, query_ids: list[str]) -> dict[str, list[QueryResponseView]]:
        found: dict[str, list[QueryResponseView]] = defaultdict(list)
        if not query_ids:
            return found
        rows = self._session.scalars(
            select(QueryResponseModel)
            .where(QueryResponseModel.query_id.in_(query_ids))
            .order_by(text("query_responses.rowid"))
        )
        for r in rows:
            found[r.query_id].append(
                QueryResponseView(r.response_id, r.author, r.message, r.created_at)
            )
        return found
