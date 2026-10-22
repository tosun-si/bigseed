from conftest import EXAMPLE_PACK
from typer.testing import CliRunner

from bigseed.cli import app


def test_given_example_pack_when_seed_dry_run_then_plan_shown_and_nothing_seeded():
    # WHEN
    result = CliRunner().invoke(app, ["seed", "uat", "-p", str(EXAMPLE_PACK), "--dry-run"])

    # THEN
    assert (result.exit_code, result.output) == (
        0,
        "my-uat-project.monitoring_uat.job_failure  <- 8 rows (monitoring.job_failure)\n",
    )


def test_given_protected_environment_when_seed_then_exit_code_2():
    # WHEN
    result = CliRunner().invoke(app, ["seed", "prod", "-p", str(EXAMPLE_PACK)])

    # THEN
    assert (result.exit_code, "not seedable" in result.output) == (2, True)
