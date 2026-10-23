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


def test_given_expected_rows_read_from_data_when_check_then_problem_and_not_ok(pack_dir):
    # GIVEN
    (pack_dir / "data/monitoring/daily_failures.json").write_text("[]")
    manifest = pack_dir / "pack.yaml"
    manifest.write_text(
        manifest.read_text().replace(
            "  monitoring.job_failure: data/monitoring/job_failure.json",
            "  monitoring.job_failure: data/monitoring/job_failure.json\n"
            "  monitoring.daily_failures: data/monitoring/daily_failures.json",
        )
    )
    test_file = pack_dir / "tests/monitoring/daily_failures.bigtesty.yaml"
    test_file.write_text(
        test_file.read_text().replace(
            """        expected:
          - { day: "2026-01-10", featureName: featurePSG, failuresCount: 3 }
          - { day: "2026-01-11", featureName: featurePSG, failuresCount: 2 }""",
            "        expected_file: ../../data/monitoring/daily_failures.json",
        )
    )

    # WHEN
    report = check_pack(load_pack(pack_dir))

    # THEN
    scenario = "monitoring/daily_failures.bigtesty.yaml::r1_one_row_per_day_and_feature_with_enough_failures"
    assert (report.ok, report.problems) == (
        False,
        (
            f"{scenario}: expected rows read from data/monitoring/daily_failures.json, the data files are seeded into "
            "the environments: write the expected rows in the then",
            "data of monitoring.daily_failures, a table checked by the then and loaded by no given: only the input "
            "tables are seeded",
        ),
    )


def test_given_scenario_without_when_when_check_then_problem_and_not_ok(pack_dir):
    # GIVEN
    test_file = pack_dir / "tests/monitoring/daily_failures.bigtesty.yaml"
    before_r2, r2_and_after = test_file.read_text().split("  - name: r2_one_failure_is_not_reported")
    test_file.write_text(
        before_r2
        + "  - name: r2_one_failure_is_not_reported"
        + r2_and_after.replace("    when:\n      sql_file: ../../inputs/build_daily_failures.sql\n", "", 1)
    )

    # WHEN
    report = check_pack(load_pack(pack_dir))

    # THEN
    assert (report.ok, report.problems) == (
        False,
        (
            "monitoring/daily_failures.bigtesty.yaml::r2_one_failure_is_not_reported: no when, the code under test "
            "never runs and the then checks the given rows only",
        ),
    )


def test_given_generation_defects_when_check_then_warnings_and_still_ok(pack_dir):
    # GIVEN a data file per scenario, a scenario covering two rules, no seedable environment
    r2 = "monitoring/daily_failures.bigtesty.yaml::r2_one_failure_is_not_reported"
    r3 = "monitoring/daily_failures.bigtesty.yaml::r3_failure_without_feature_is_ignored"
    (pack_dir / "data/monitoring/r2_job_failure.json").write_text("[]")

    test_file = pack_dir / "tests/monitoring/daily_failures.bigtesty.yaml"
    before_r2, r2_and_after = test_file.read_text().split("  - name: r2_one_failure_is_not_reported")
    test_file.write_text(
        before_r2
        + "  - name: r2_one_failure_is_not_reported"
        + r2_and_after.replace("job_failure.json", "r2_job_failure.json", 1)
    )

    manifest = pack_dir / "pack.yaml"
    content = manifest.read_text().replace(f"scenarios: [{r2}]", f"scenarios: [{r2}, {r3}]")
    manifest.write_text(content[: content.index("environments:")])

    # WHEN
    report = check_pack(load_pack(pack_dir))

    # THEN
    assert (report.ok, report.warnings) == (
        True,
        (
            f"{r2}: the given of monitoring.job_failure reads data/monitoring/r2_job_failure.json, not the data file "
            "of the table: the tests and the seeded environments have different rows",
            "data/monitoring/r2_job_failure.json is in data/ but in no table of the manifest",
            f"{r3} covers R2, R3: one scenario per rule shows which rule fails",
            "no seedable environment in the manifest: the pack runs the tests, it can't seed an environment",
        ),
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
