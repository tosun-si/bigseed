import pytest
from conftest import EXAMPLE_PACK, FakeBigQueryClient

from bigseed.errors import SeedError
from bigseed.pack import load_pack
from bigseed.seed import SeedStep, seed, seed_plan


def test_given_seedable_environment_when_seed_plan_then_input_tables_of_the_environment():
    # WHEN
    steps = seed_plan(load_pack(EXAMPLE_PACK), "uat")

    # THEN
    assert steps == (SeedStep("monitoring.job_failure", "my-uat-project.monitoring_uat.job_failure", 8),)


@pytest.mark.parametrize(
    ("environment", "error_message"),
    [
        # --- Case 1: environment protected with seedable: false ---
        ("prod", "not seedable"),
        # --- Case 2: environment not declared in the pack ---
        ("dev", "Unknown environment dev, declared: uat, prod"),
    ],
)
def test_given_protected_or_unknown_environment_when_seed_plan_then_seed_error(environment, error_message):
    # WHEN / THEN
    with pytest.raises(SeedError, match=error_message):
        seed_plan(load_pack(EXAMPLE_PACK), environment)


def test_given_environment_when_seed_then_rows_replaced_with_the_schema_of_the_environment():
    # GIVEN
    client = FakeBigQueryClient()

    # WHEN
    seed(load_pack(EXAMPLE_PACK), "uat", client)  # type: ignore[arg-type]

    # THEN
    [load] = client.loads
    assert (
        load["destination"],
        len(load["rows"]),
        load["config"].write_disposition,
        load["config"].schema,
        load["config"].labels,
    ) == (
        "my-uat-project.monitoring_uat.job_failure",
        8,
        "WRITE_TRUNCATE",
        client.schema,
        {"bigseed": "true", "bigseed_pack_version": "1"},
    )
