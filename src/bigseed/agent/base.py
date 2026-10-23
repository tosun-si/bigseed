"""
The generation of a pack, behind an interface: the ADK agent is one implementation, another framework (LangGraph...)
or a deterministic generator can be another one.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google.cloud import bigquery

from bigseed.errors import BigSeedError
from bigseed.pack import sha256


@dataclass(frozen=True)
class SourceFile:
    """An input of the generation: SQL, Python, Java, a Markdown spec..."""

    path: Path
    content: str
    sha256: str


@dataclass(frozen=True)
class GenerationRequest:
    sources: tuple[SourceFile, ...]
    # The BigQuery schemas of the tables the rules read and write, dataset.table -> BigQuery JSON schema: the data
    # is generated with the real types and modes.
    schemas: dict[str, list[dict[str, Any]]]
    output_dir: Path
    pack_name: str
    # The BigQuery location of the datasets, e.g. EU.
    location: str
    # The environments of the manifest, name -> {project, datasets}: given, never guessed by the model.
    environments: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationStats:
    """What a generation cost: where the time and the tokens go."""

    model_calls: int
    tool_calls: int
    prompt_tokens: int
    output_tokens: int
    # The reasoning tokens of the thinking models, billed as output tokens.
    thinking_tokens: int
    seconds: float


# Writes a pack in request.output_dir, to be checked with `bigseed check` and reviewed before approval.
PackGenerator = Callable[[GenerationRequest], GenerationStats]


def read_sources(paths: list[Path]) -> tuple[SourceFile, ...]:
    return tuple(SourceFile(path, path.read_text(), sha256(path)) for path in paths)


def parse_table_option(option: str) -> tuple[str, str]:
    """
    `monitoring.job_failure=my-project.monitoring_uat.job_failure`: the table of the pack and the table to read its
    schema from. `my-project.monitoring.job_failure` alone: the pack table is `monitoring.job_failure`.
    """
    pack_table, _, source = option.rpartition("=")
    return (pack_table or ".".join(source.split(".")[-2:]), source)


def read_tables(client: bigquery.Client, tables: dict[str, str]) -> dict[str, bigquery.Table]:
    """Pack table (dataset.table) -> its source table, with its schema and location. The rows are never read."""
    return {pack_table: client.get_table(source) for pack_table, source in tables.items()}


def schemas_of(tables: dict[str, bigquery.Table]) -> dict[str, list[dict[str, Any]]]:
    return {pack_table: [field.to_api_repr() for field in table.schema] for pack_table, table in tables.items()}


def location_of(tables: dict[str, bigquery.Table]) -> str:
    """The location of the datasets, for bigtesty.yaml: the tables of a pack are in one location."""
    locations = sorted({table.location for table in tables.values() if table.location})
    if len(locations) != 1:
        raise BigSeedError(f"The tables of a pack must be in one location, found: {', '.join(locations) or 'none'}")
    return locations[0]


def environment_from_tables(tables: dict[str, str]) -> dict[str, Any]:
    """
    The environment the source tables of the --table options belong to: their project, and the dataset of each
    dataset of the pack (monitoring.job_failure=my-uat.monitoring_uat.job_failure -> monitoring: monitoring_uat).
    """
    sources = [source.split(".") for source in tables.values()]
    projects = sorted({parts[0] for parts in sources if len(parts) == 3})
    if len(projects) != 1 or any(len(parts) != 3 for parts in sources):
        raise BigSeedError(
            "--env needs every --table read from one project, as project.dataset.table: "
            f"found {', '.join(projects) or 'no project'}"
        )

    datasets = {(pack_table.split(".")[0], source.split(".")[1]) for pack_table, source in tables.items()}
    if len({dataset for dataset, _ in datasets}) != len(datasets):
        raise BigSeedError(f"--env needs one source dataset per dataset of the pack, found: {sorted(datasets)}")
    return {"project": projects[0], "datasets": dict(sorted(datasets))}
