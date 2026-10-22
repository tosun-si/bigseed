"""
The generation of a pack, behind an interface: the ADK agent is one implementation, another framework (LangGraph...)
or a deterministic generator can be another one.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

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


class PackGenerator(Protocol):
    def generate(self, request: GenerationRequest) -> None:
        """Writes a pack in request.output_dir, to be checked with `bigseed check` and reviewed before approval."""


def read_sources(paths: list[Path]) -> tuple[SourceFile, ...]:
    return tuple(SourceFile(path, path.read_text(), sha256(path)) for path in paths)


def read_schemas(client: bigquery.Client, tables: list[str]) -> dict[str, list[dict[str, Any]]]:
    """`project.dataset.table` -> its schema, keyed by `dataset.table` as in the pack. The rows are never read."""
    schemas = {}
    for table_ref in tables:
        table = client.get_table(table_ref)
        schemas[f"{table.dataset_id}.{table.table_id}"] = [field.to_api_repr() for field in table.schema]
    return schemas
