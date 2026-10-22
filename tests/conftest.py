import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from google.cloud import bigquery

EXAMPLE_PACK = Path(__file__).parents[1] / "examples" / "01-daily-failures"


@pytest.fixture
def pack_dir(tmp_path: Path) -> Path:
    """A copy of the example pack, to change it in a test."""
    return Path(shutil.copytree(EXAMPLE_PACK, tmp_path / "pack"))


@dataclass
class FakeLoadJob:
    def result(self) -> None:
        return None


@dataclass
class FakeBigQueryClient:
    schema: list[bigquery.SchemaField] = field(default_factory=lambda: [bigquery.SchemaField("featureName", "STRING")])
    loads: list[dict[str, Any]] = field(default_factory=list)

    def get_table(self, table_ref: str) -> bigquery.Table:
        return bigquery.Table(table_ref, schema=self.schema)

    def load_table_from_json(self, rows: list[dict[str, Any]], destination: str, job_config: Any) -> FakeLoadJob:
        self.loads.append({"rows": rows, "destination": destination, "config": job_config})
        return FakeLoadJob()
