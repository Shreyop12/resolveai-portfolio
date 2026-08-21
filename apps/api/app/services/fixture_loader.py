import json
from pathlib import Path

from app.schemas.fixture import (
    DeploymentRecord,
    ExpectedRootCause,
    LogEvent,
    MetricPoint,
    ScenarioManifest,
    SyntheticIncidentFixture,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
FIXTURES_ROOT = PROJECT_ROOT / "fixtures" / "incidents"


class FixtureNotFoundError(FileNotFoundError):
    """Raised when a requested synthetic scenario does not exist."""


def list_fixture_ids() -> list[str]:
    """Return stable fixture IDs without loading every evidence file."""
    if not FIXTURES_ROOT.exists():
        return []
    return sorted(path.name for path in FIXTURES_ROOT.iterdir() if path.is_dir())


def load_fixture(scenario_id: str) -> SyntheticIncidentFixture:
    """Load one complete synthetic incident case and validate its links."""
    fixture_path = FIXTURES_ROOT / scenario_id
    if not fixture_path.is_dir():
        raise FixtureNotFoundError(f"Synthetic fixture '{scenario_id}' was not found.")

    fixture = SyntheticIncidentFixture(
        manifest=_load_json(fixture_path / "scenario.json", ScenarioManifest),
        logs=_load_json_list(fixture_path / "logs.json", LogEvent),
        metrics=_load_json_list(fixture_path / "metrics.json", MetricPoint),
        deployment=_load_json(fixture_path / "deployment.json", DeploymentRecord),
        expected_root_cause=_load_json(
            fixture_path / "expected_root_cause.json", ExpectedRootCause
        ),
        git_diff=(fixture_path / "git_diff.patch").read_text(encoding="utf-8"),
    )
    fixture.validate_evidence_references()
    return fixture


def _load_json(path: Path, schema: type[ScenarioManifest] | type[DeploymentRecord] | type[ExpectedRootCause]):
    return schema.model_validate_json(path.read_text(encoding="utf-8"))


def _load_json_list(path: Path, schema: type[LogEvent] | type[MetricPoint]) -> list[LogEvent] | list[MetricPoint]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [schema.model_validate(item) for item in data]
