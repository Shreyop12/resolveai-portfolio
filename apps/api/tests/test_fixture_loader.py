import pytest

from app.services.fixture_loader import FixtureNotFoundError, list_fixture_ids, load_fixture


def test_loads_complete_redis_misconfiguration_fixture() -> None:
    fixture = load_fixture("deployment_redis_misconfiguration")

    assert fixture.manifest.incident.title == "Production API returning 500 errors"
    assert fixture.deployment.completed_at < fixture.logs[1].timestamp
    assert "REDIS_URL=redis//redis:6379/0" in fixture.git_diff
    assert fixture.expected_root_cause.confidence == 0.92
    assert set(fixture.expected_root_cause.evidence_ids) <= fixture.evidence_ids


def test_fixture_ids_are_discoverable() -> None:
    assert list_fixture_ids() == ["deployment_redis_misconfiguration"]


def test_unknown_fixture_is_rejected() -> None:
    with pytest.raises(FixtureNotFoundError):
        load_fixture("does_not_exist")
