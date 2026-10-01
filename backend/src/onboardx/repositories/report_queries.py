"""Read-only report SQL over state_history, decisions and overrides (AC-10, NFR-01, NFR-03).

Every query starts from the ``cohort`` CTE (cases that started inside the filters) and returns
plain integers and strings. Only ``case_id``, ``product`` and state columns are touched: name,
contact and every other PII column are never selected. Averages are integer sums divided in
Python with floor division; there is no ``avg()`` and no float anywhere.
"""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from onboardx.domain.reports import ReportFilters

COHORT = """WITH cohort AS (
  SELECT c.case_id AS case_id, c.product AS product, h.created_at AS started_at
  FROM cases c
  JOIN state_history h ON h.case_id = c.case_id AND h.from_state IS NULL
  WHERE (:product IS NULL OR c.product = :product)
    AND (:start IS NULL OR h.created_at >= :start)
    AND (:stop IS NULL OR h.created_at < :stop))
"""

TAT_SQL = (
    COHORT
    + """
SELECT product, COUNT(*), SUM(secs), MIN(secs), MAX(secs) FROM (
  SELECT cohort.product AS product,
    CAST(strftime('%s', e.created_at) AS INTEGER)
      - CAST(strftime('%s', cohort.started_at) AS INTEGER) AS secs
  FROM cohort JOIN state_history e
    ON e.case_id = cohort.case_id AND e.to_state IN ('APPROVED', 'REJECTED'))
GROUP BY product ORDER BY product"""
)

FUNNEL_SQL = (
    COHORT
    + """
SELECT h.to_state, COUNT(DISTINCT h.case_id)
FROM cohort JOIN state_history h ON h.case_id = cohort.case_id
GROUP BY h.to_state"""
)

BACKLOG_SQL = (
    COHORT
    + """
SELECT h.created_at FROM cohort
JOIN cases c ON c.case_id = cohort.case_id AND c.state = 'MANUAL_REVIEW'
JOIN state_history h ON h.case_id = cohort.case_id AND h.to_state = 'MANUAL_REVIEW'
ORDER BY h.created_at"""
)

STAGE_SQL = (
    COHORT
    + """
SELECT from_state, to_state, COUNT(*), SUM(secs) FROM (
  SELECT h.from_state AS from_state, h.to_state AS to_state,
    CAST(strftime('%s', h.created_at) AS INTEGER) - CAST(strftime('%s', LAG(h.created_at)
      OVER (PARTITION BY h.case_id ORDER BY h.seq)) AS INTEGER) AS secs
  FROM state_history h JOIN cohort ON cohort.case_id = h.case_id)
WHERE from_state IS NOT NULL
GROUP BY from_state, to_state ORDER BY from_state, to_state"""
)

REASONS_SQL = (
    COHORT
    + """
SELECT o.reason_code, COUNT(*) FROM overrides o
JOIN cohort ON cohort.case_id = o.case_id
WHERE o.decision = 'REJECT'
GROUP BY o.reason_code ORDER BY COUNT(*) DESC, o.reason_code ASC LIMIT :limit"""
)

AUTO_SQL = (
    COHORT
    + """
SELECT COUNT(*), COALESCE(SUM(CASE WHEN d.outcome = 'APPROVED' THEN 1 ELSE 0 END), 0)
FROM decisions d JOIN cohort ON cohort.case_id = d.case_id"""
)

DROPPED_SQL = """
SELECT c.state, COUNT(*) FROM cases c
WHERE c.state IN ('INITIATED', 'DOCS_SUBMITTED')
  AND (:product IS NULL OR c.product = :product)
  AND (SELECT MAX(h.created_at) FROM state_history h WHERE h.case_id = c.case_id) < :cutoff
GROUP BY c.state"""


def _start(day: date | None) -> str | None:
    return None if day is None else f"{day.isoformat()}T00:00:00Z"


def _stop(day: date | None) -> str | None:
    """Exclusive upper bound: midnight after the inclusive ``to`` date."""
    return None if day is None else f"{(day + timedelta(days=1)).isoformat()}T00:00:00Z"


def _params(filters: ReportFilters) -> dict[str, Any]:
    return {
        "product": None if filters.product is None else str(filters.product),
        "start": _start(filters.date_from),
        "stop": _stop(filters.date_to),
    }


class ReportQueries:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _rows(self, sql: str, params: dict[str, Any]) -> list[Any]:
        return list(self._session.execute(text(sql), params))

    def tat(self, filters: ReportFilters) -> list[tuple[str, int, int, int, int]]:
        """(product, count, sum_seconds, min_seconds, max_seconds) of closed cases."""
        return [
            (str(r[0]), int(r[1]), int(r[2]), int(r[3]), int(r[4]))
            for r in self._rows(TAT_SQL, _params(filters))
        ]

    def funnel_counts(self, filters: ReportFilters) -> dict[str, int]:
        """Cases that ever reached each state."""
        return {str(r[0]): int(r[1]) for r in self._rows(FUNNEL_SQL, _params(filters))}

    def backlog_entries(self, filters: ReportFilters) -> list[str]:
        """Entry timestamps (into MANUAL_REVIEW) of cases that are still in MANUAL_REVIEW."""
        return [str(r[0]) for r in self._rows(BACKLOG_SQL, _params(filters))]

    def stage_durations(self, filters: ReportFilters) -> list[tuple[str, str, int, int]]:
        """(from_state, to_state, count, sum_seconds) over consecutive transitions."""
        return [
            (str(r[0]), str(r[1]), int(r[2]), int(r[3]))
            for r in self._rows(STAGE_SQL, _params(filters))
        ]

    def rejection_reasons(self, filters: ReportFilters, limit: int) -> list[tuple[str, int]]:
        params = {**_params(filters), "limit": limit}
        return [(str(r[0]), int(r[1])) for r in self._rows(REASONS_SQL, params)]

    def decision_counts(self, filters: ReportFilters) -> tuple[int, int]:
        """(decided, auto_approved) over cases with a decision row."""
        row = self._rows(AUTO_SQL, _params(filters))[0]
        return int(row[0]), int(row[1])

    def dropped(self, product: str | None, cutoff: str) -> dict[str, int]:
        """Open INITIATED / DOCS_SUBMITTED cases whose last activity is before ``cutoff``."""
        rows = self._rows(DROPPED_SQL, {"product": product, "cutoff": cutoff})
        return {str(r[0]): int(r[1]) for r in rows}
