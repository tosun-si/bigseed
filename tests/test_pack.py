import pytest

from bigseed.check import check_pack
from bigseed.errors import PackError
from bigseed.pack import load_pack


def test_given_example_pack_when_check_then_every_rule_covered():
    # GIVEN
    from conftest import EXAMPLE_PACK

    # WHEN
    report = check_pack(load_pack(EXAMPLE_PACK))

    # THEN
    assert ([(r.rule_id, r.covered) for r in report.coverage], report.stale_sources, report.scenarios_without_rule) == (
        [("R1", True), ("R2", True), ("R3", True)],
        (),
        (),
    )


def test_given_changed_input_when_check_then_stale_source(pack_dir):
    # GIVEN
    (pack_dir / "inputs/build_daily_failures.sql").write_text("SELECT 1")

    # WHEN
    report = check_pack(load_pack(pack_dir))

    # THEN
    assert report.stale_sources == ("inputs/build_daily_failures.sql",)


def test_given_rule_without_scenario_when_check_then_uncovered_and_scenario_without_rule(pack_dir):
    # GIVEN
    manifest = pack_dir / "pack.yaml"
    manifest.write_text(
        manifest.read_text().replace(
            "scenarios: [monitoring/daily_failures.bigtesty.yaml::r3_failure_without_feature_is_ignored]",
            "scenarios: []",
        )
    )

    # WHEN
    report = check_pack(load_pack(pack_dir))

    # THEN
    assert ([r.rule_id for r in report.coverage if not r.covered], report.scenarios_without_rule) == (
        ["R3"],
        ("monitoring/daily_failures.bigtesty.yaml::r3_failure_without_feature_is_ignored",),
    )


@pytest.mark.parametrize(
    ("old", "new", "error_message"),
    [
        # --- Case 1: rule referencing an unknown scenario ---
        ("::r2_one_failure_is_not_reported]", "::unknown]", "Rules referencing unknown scenarios"),
        # --- Case 2: missing data file ---
        ("data/monitoring/job_failure.json", "data/missing.json", "Cannot read the data file"),
        # --- Case 3: no rule ---
        ("rules:\n", "rules: []\nother_rules:\n", "Invalid"),
    ],
)
def test_given_invalid_pack_when_check_then_pack_error(pack_dir, old, new, error_message):
    # GIVEN
    manifest = pack_dir / "pack.yaml"
    manifest.write_text(manifest.read_text().replace(old, new, 1))

    # WHEN / THEN
    with pytest.raises(PackError, match=error_message):
        check_pack(load_pack(pack_dir))
