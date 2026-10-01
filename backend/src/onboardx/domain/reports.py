"""Report value objects and integer-only arithmetic (AC-10, NFR-01).

Durations are whole seconds (or minutes for ages), ratios are basis points. Averages use
floor division; nothing here ever produces a fractional number.
"""

from dataclasses import dataclass
from datetime import date

from onboardx.domain.enums import CaseState, Product
from onboardx.domain.errors import ValidationError

AUTO_APPROVAL_TARGET_BP = 6000
BASIS_POINTS = 10000
SECONDS_PER_MINUTE = 60
MAX_REASONS = 5
FUNNEL_STAGES: tuple[CaseState, ...] = (
    CaseState.INITIATED,
    CaseState.DOCS_SUBMITTED,
    CaseState.SCREENED,
    CaseState.CLASSIFIED,
    CaseState.MANUAL_REVIEW,
    CaseState.APPROVED,
    CaseState.REJECTED,
)
PIPELINE_CHAIN = FUNNEL_STAGES[:4]
BUCKETS: tuple[tuple[str, int, int | None], ...] = (
    ("under_60", 0, 59),
    ("60_to_1440", 60, 1440),
    ("over_1440", 1441, None),
)
DROPPABLE_STATES = (CaseState.INITIATED, CaseState.DOCS_SUBMITTED)


@dataclass(frozen=True)
class ReportFilters:
    """Optional product and inclusive date range (UTC dates)."""

    product: Product | None = None
    date_from: date | None = None
    date_to: date | None = None

    def __post_init__(self) -> None:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError.single("from", "from must not be after to")


@dataclass(frozen=True)
class TatRow:
    product: str
    count: int
    avg_seconds: int
    min_seconds: int
    max_seconds: int


@dataclass(frozen=True)
class FunnelStage:
    stage: str
    count: int
    conversion_bp: int


@dataclass(frozen=True)
class BacklogBucket:
    label: str
    min_minutes: int
    max_minutes: int | None
    count: int


@dataclass(frozen=True)
class Backlog:
    count: int
    oldest_age_minutes: int
    buckets: tuple[BacklogBucket, ...]


@dataclass(frozen=True)
class StageTime:
    from_state: str
    to_state: str
    count: int
    avg_seconds: int


@dataclass(frozen=True)
class ReasonCount:
    reason_code: str
    count: int


@dataclass(frozen=True)
class AutoApproval:
    auto_approved: int
    decided: int
    rate_bp: int
    target_bp: int
    met: bool


@dataclass(frozen=True)
class DroppedStage:
    stage: str
    count: int


def floor_avg(total: int, count: int) -> int:
    """Floor of total / count; zero when there is nothing to average."""
    return total // count if count else 0


def ratio_bp(numerator: int, denominator: int) -> int:
    """Floor of numerator / denominator in basis points; zero for an empty denominator."""
    return numerator * BASIS_POINTS // denominator if denominator else 0


def bucket_counts(ages_minutes: list[int]) -> tuple[BacklogBucket, ...]:
    """Count ages into the under-60, 60-1440 and over-1440 minute buckets."""
    out: list[BacklogBucket] = []
    for label, low, high in BUCKETS:
        count = sum(1 for age in ages_minutes if age >= low and (high is None or age <= high))
        out.append(BacklogBucket(label, low, high, count))
    return tuple(out)


def build_backlog(ages_minutes: list[int]) -> Backlog:
    return Backlog(len(ages_minutes), max(ages_minutes, default=0), bucket_counts(ages_minutes))


def build_funnel(counts: dict[str, int]) -> tuple[FunnelStage, ...]:
    """Conversion from the previous stage; MANUAL_REVIEW and outcomes convert from CLASSIFIED."""
    classified = counts.get(str(CaseState.CLASSIFIED), 0)
    previous = 0
    out: list[FunnelStage] = []
    for stage in FUNNEL_STAGES:
        count = counts.get(str(stage), 0)
        if stage is CaseState.INITIATED:
            bp = BASIS_POINTS if count else 0
        elif stage in PIPELINE_CHAIN:
            bp = ratio_bp(count, previous)
        else:
            bp = ratio_bp(count, classified)
        if stage in PIPELINE_CHAIN:
            previous = count
        out.append(FunnelStage(str(stage), count, bp))
    return tuple(out)


def build_auto_approval(auto_approved: int, decided: int) -> AutoApproval:
    rate = ratio_bp(auto_approved, decided)
    return AutoApproval(
        auto_approved, decided, rate, AUTO_APPROVAL_TARGET_BP, rate >= AUTO_APPROVAL_TARGET_BP
    )


def age_minutes(now_epoch: int, then_epoch: int) -> int:
    """Whole minutes between two epoch-second values, never negative."""
    return max(now_epoch - then_epoch, 0) // SECONDS_PER_MINUTE
