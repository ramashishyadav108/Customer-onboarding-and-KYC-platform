"""AC-06 / NFR-08 / E3-S2: rule-set lifecycle and immutability at service AND trigger level."""

import json

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DatabaseError

from helpers import FakeClock
from onboardx.controllers.dependencies.services import Services
from onboardx.domain.enums import RuleSetStatus
from onboardx.domain.errors import (
    DraftExistsError,
    NotFoundError,
    PublishedRuleSetImmutableError,
    RuleSetInvalidError,
    ValidationError,
)
from onboardx.domain.ruleset_codec import ruleset_to_dict
from onboardx.repositories.unit_of_work import UnitOfWorkFactory
from ruleset_fixture import V1_DICT


def version_row(engine: Engine, version: int) -> dict[str, object]:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM risk_rule_sets WHERE version=:v"), {"v": version})
        return dict(row.one()._mapping)


@pytest.mark.ac("AC-06")
def test_ac06_4_new_version_is_a_draft_copy_of_the_latest(services: Services) -> None:
    """AC-06.4: create_draft copies v1 into DRAFT v2 (version = max + 1)."""
    draft = services.rule_sets.create_draft("admin1")
    assert draft.version == 2 and draft.status is RuleSetStatus.DRAFT
    assert draft.published_at is None and draft.author == "admin1"
    copied = ruleset_to_dict(draft)
    for key in ("weights", "points", "geography_map", "border_states", "thresholds"):
        assert copied[key] == V1_DICT[key]


@pytest.mark.ac("AC-06")
def test_ac06_4_old_versions_stay_readable_and_unchanged(
    services: Services, engine: Engine
) -> None:
    """AC-06.4: earlier versions stay queryable and unchanged after a draft and a publish."""
    before = version_row(engine, 1)
    services.rule_sets.create_draft("admin1")
    services.rule_sets.update_draft(2, {"thresholds": {"low_max": 20, "medium_max": 50}}, "admin1")
    services.rule_sets.publish(2, "admin1")
    assert version_row(engine, 1) == before
    assert [r.version for r in services.rule_sets.list_rule_sets()] == [1, 2]
    assert services.rule_sets.get(1).low_max == 29


@pytest.mark.ac("AC-06")
def test_ac06_4_only_one_draft_at_a_time(services: Services) -> None:
    """DD-11: a second draft while one exists raises DraftExistsError."""
    services.rule_sets.create_draft("admin1")
    with pytest.raises(DraftExistsError):
        services.rule_sets.create_draft("admin1")


@pytest.mark.ac("AC-06")
def test_ac06_3_publish_sets_status_and_published_at(services: Services, clock: FakeClock) -> None:
    """AC-06.3: publish sets PUBLISHED and published_at."""
    services.rule_sets.create_draft("admin1")
    published = services.rule_sets.publish(2, "admin1")
    assert published.status is RuleSetStatus.PUBLISHED
    assert published.published_at is not None and published.published_at.endswith("Z")


@pytest.mark.ac("AC-06")
@pytest.mark.nfr("NFR-08")
def test_nfr08_service_refuses_update_of_a_published_rule_set(services: Services) -> None:
    """AC-06.3 / NFR-08: updating published v1 raises PublishedRuleSetImmutableError."""
    with pytest.raises(PublishedRuleSetImmutableError) as info:
        services.rule_sets.update_draft(1, {"weights": {"age": 1}}, "admin1")
    assert info.value.code == "RULESET_IMMUTABLE" and info.value.details == {"version": 1}


@pytest.mark.ac("AC-06")
@pytest.mark.nfr("NFR-08")
def test_nfr08_service_refuses_delete_and_republish_of_a_published_rule_set(
    services: Services,
) -> None:
    """AC-06.3 / NFR-08: delete and a second publish of v1 both raise."""
    with pytest.raises(PublishedRuleSetImmutableError):
        services.rule_sets.delete_draft(1)
    with pytest.raises(PublishedRuleSetImmutableError):
        services.rule_sets.publish(1, "admin1")


@pytest.mark.ac("AC-06")
@pytest.mark.nfr("NFR-08")
def test_nfr08_repository_translates_the_database_trigger(
    uow_factory: UnitOfWorkFactory, services: Services
) -> None:
    """NFR-08: bypassing the service, the repo call hits the trigger -> immutability error."""
    with uow_factory() as uow:
        v1 = uow.rule_sets.get(1)
        assert v1 is not None
        with pytest.raises(PublishedRuleSetImmutableError):
            uow.rule_sets.update_draft(v1)
        with pytest.raises(PublishedRuleSetImmutableError):
            uow.rule_sets.delete(1)
        with pytest.raises(PublishedRuleSetImmutableError):
            uow.rule_sets.mark_published(1, "2030-01-01T00:00:00Z")


@pytest.mark.ac("AC-06")
@pytest.mark.nfr("NFR-08")
@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE risk_rule_sets SET low_max = 1 WHERE version = 1",
        "UPDATE risk_rule_sets SET status = 'DRAFT', published_at = NULL WHERE version = 1",
        "DELETE FROM risk_rule_sets WHERE version = 1",
    ],
)
def test_nfr08_database_trigger_blocks_published_update_and_delete(
    engine: Engine, sql: str
) -> None:
    """AC-06.3 / NFR-08: raw SQL on a PUBLISHED rule set is rejected by trigger."""
    with engine.connect() as conn:
        with pytest.raises(DatabaseError, match="published rule set is immutable"):
            conn.execute(text(sql))
        conn.rollback()
    assert version_row(engine, 1)["low_max"] == 29


@pytest.mark.ac("AC-06")
@pytest.mark.nfr("NFR-08")
def test_nfr08_database_trigger_blocks_inserting_a_published_rule_set(engine: Engine) -> None:
    """NFR-08: rule sets enter as DRAFT; a direct PUBLISHED insert is rejected."""
    with engine.connect() as conn:
        with pytest.raises(DatabaseError):
            conn.execute(
                text(
                    "INSERT INTO risk_rule_sets (version, status, weights, points, geography_map,"
                    " geography_default, border_states, low_max, medium_max, author, created_at,"
                    " published_at) VALUES (2, 'PUBLISHED', '{}', '{}', '{}', 'X', '[]', 1, 2,"
                    " 'a', 't', 't')"
                )
            )
        conn.rollback()


@pytest.mark.ac("AC-06")
def test_ac06_draft_remains_editable_at_database_level(engine: Engine, services: Services) -> None:
    """AC-06.11: a DRAFT can be updated and deleted; only PUBLISHED is frozen."""
    services.rule_sets.create_draft("admin1")
    with engine.begin() as conn:
        conn.execute(text("UPDATE risk_rule_sets SET low_max = 5 WHERE version = 2"))
        conn.execute(text("DELETE FROM risk_rule_sets WHERE version = 2"))
    assert services.rule_sets.list_rule_sets()[-1].version == 1


@pytest.mark.ac("AC-06")
def test_ac06_5_publish_fails_with_ruleset_invalid(services: Services) -> None:
    """AC-06.5: weights not summing to 100 or bad thresholds fail with the reasons."""
    services.rule_sets.create_draft("admin1")
    services.rule_sets.update_draft(
        2,
        {
            "weights": {"age": 30, "income_band": 25, "occupation_category": 30, "geography": 25},
            "thresholds": {"low_max": 60, "medium_max": 59},
        },
        "admin1",
    )
    with pytest.raises(RuleSetInvalidError) as info:
        services.rule_sets.publish(2, "admin1")
    assert info.value.reasons == ["WEIGHTS_SUM", "THRESHOLDS_ORDER"]
    assert services.rule_sets.get(2).status is RuleSetStatus.DRAFT


@pytest.mark.ac("AC-06")
@pytest.mark.nfr("NFR-01")
def test_ac06_2_draft_update_rejects_fractional_weights(services: Services) -> None:
    """AC-06.2: a draft edit with 0.25 raises ValidationError and stores nothing."""
    services.rule_sets.create_draft("admin1")
    with pytest.raises(ValidationError):
        services.rule_sets.update_draft(
            2, {"weights": {"age": 0.25, "income_band": 25, "occupation_category": 30,
                            "geography": 25}}, "admin1",
        )  # fmt: skip
    assert services.rule_sets.get(2).weights["age"] == 20


@pytest.mark.ac("AC-06")
def test_ac06_unknown_version_is_not_found(services: Services) -> None:
    """AC-06: unknown versions raise NotFoundError."""
    for call in (
        lambda: services.rule_sets.get(99),
        lambda: services.rule_sets.publish(99, "a"),
        lambda: services.rule_sets.update_draft(99, {}, "a"),
    ):
        with pytest.raises(NotFoundError):
            call()


@pytest.mark.ac("AC-06")
def test_ac06_rule_set_changes_are_audited(
    services: Services, uow_factory: UnitOfWorkFactory
) -> None:
    """Audit catalogue: RULESET_DRAFT_CREATED, _UPDATED and _PUBLISHED carry actor and version."""
    services.rule_sets.create_draft("admin1")
    services.rule_sets.update_draft(2, {"border_states": ["JK"]}, "admin1")
    services.rule_sets.publish(2, "admin1")
    with uow_factory() as uow:
        created = uow.audit.list_by_event("RULESET_DRAFT_CREATED")
        updated = uow.audit.list_by_event("RULESET_DRAFT_UPDATED")
        published = uow.audit.list_by_event("RULESET_PUBLISHED")
    assert [len(created), len(updated), len(published)] == [1, 1, 1]
    assert published[0].actor == "admin1" and published[0].payload == {"version": 2}
    stored = json.loads(json.dumps(published[0].payload))
    assert stored == {"version": 2}
