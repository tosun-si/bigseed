"""
Seeds an environment from a pack: each data file replaces the rows of its table, with a load job (free, and the rows
are immediately available). Only the environments declared in the pack and seedable can be seeded.
"""

from dataclasses import dataclass

from google.cloud import bigquery

from bigseed.errors import SeedError
from bigseed.pack import Environment, Pack, load_rows

JOB_LABELS = {"bigseed": "true"}


@dataclass(frozen=True)
class SeedStep:
    table: str
    # The table of the environment, project.dataset.table.
    target: str
    rows: int


def seed_plan(pack: Pack, environment: str) -> tuple[SeedStep, ...]:
    """What `seed` would do, without calling BigQuery."""
    env = pack.manifest.environments.get(environment)
    if env is None:
        raise SeedError(
            f"Unknown environment {environment}, declared: {', '.join(pack.manifest.environments) or 'none'}"
        )
    if not env.seedable:
        raise SeedError(f"The environment {environment} is not seedable (seedable: false)")

    unmapped = sorted({table.split(".")[0] for table in pack.manifest.data} - set(env.datasets))
    if unmapped:
        raise SeedError(f"Datasets without dataset in the environment {environment}: {', '.join(unmapped)}")

    return tuple(
        SeedStep(table, _target(env, table), len(load_rows(pack.data_file(table)))) for table in pack.manifest.data
    )


def _target(env: Environment, table: str) -> str:
    dataset, table_id = table.split(".")
    return f"{env.project}.{env.datasets[dataset]}.{table_id}"


def seed(pack: Pack, environment: str, client: bigquery.Client) -> tuple[SeedStep, ...]:
    """
    Replaces the rows of the tables of the environment by the rows of the pack. The tables must exist: their schema
    is the one of the environment, a row that doesn't match it fails the seed.
    """
    steps = seed_plan(pack, environment)
    labels = {**JOB_LABELS, "bigseed_pack_version": str(pack.manifest.version)}

    for step in steps:
        table = client.get_table(step.target)
        config = bigquery.LoadJobConfig(
            schema=table.schema,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            labels=labels,
        )
        client.load_table_from_json(load_rows(pack.data_file(step.table)), step.target, job_config=config).result()

    return steps
