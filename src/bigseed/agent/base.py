"""
The generation of a pack, behind an interface: the ADK agent is one implementation, another framework (LangGraph...)
or a deterministic generator can be another one.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.cloud import bigquery

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


# Writes a pack in request.output_dir, to be checked with `bigseed check` and reviewed before approval.
PackGenerator = Callable[[GenerationRequest], None]


def read_sources(paths: list[Path]) -> tuple[SourceFile, ...]:
    return tuple(SourceFile(path, path.read_text(), sha256(path)) for path in paths)


def parse_table_option(option: str) -> tuple[str, str]:
    """
    `monitoring.job_failure=my-project.monitoring_uat.job_failure`: the table of the pack and the table to read its
    schema from. `my-project.monitoring.job_failure` alone: the pack table is `monitoring.job_failure`.
    """
    pack_table, _, source = option.rpartition("=")
    return (pack_table or ".".join(source.split(".")[-2:]), source)


def read_schemas(client: bigquery.Client, tables: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    """Pack table (dataset.table) -> the schema of its source table. The rows are never read."""
    return {
        pack_table: [field.to_api_repr() for field in client.get_table(source).schema]
        for pack_table, source in tables.items()
    }
