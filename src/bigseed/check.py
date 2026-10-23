"""
Checks a pack before its approval: the manifest, the data files, the BigTesty project, the coverage of the rules by
the scenarios, and the inputs changed since the generation. No call to BigQuery: the scenarios are run by BigTesty.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from bigtesty.api import Project
from bigtesty.exceptions import BigTestyError

from bigseed.errors import PackError
from bigseed.pack import Pack, load_rows, sha256

TEST_FILE_SUFFIXES = (".bigtesty.yaml", ".bigtesty.yml", ".bigtesty.json")


@dataclass(frozen=True)
class RuleCoverage:
    rule_id: str
    description: str
    scenarios: tuple[str, ...]

    @property
    def covered(self) -> bool:
        return bool(self.scenarios)


@dataclass(frozen=True)
class PackReport:
    coverage: tuple[RuleCoverage, ...]
    # Inputs changed or removed since the generation: the pack may not match the code anymore.
    stale_sources: tuple[str, ...] = ()
    # Tests whose scenarios are covered by no rule: generated without a business reason, to review.
    scenarios_without_rule: tuple[str, ...] = ()
    # The pack breaks a principle of BigSeed: it can't be approved.
    problems: tuple[str, ...] = ()
    # Allowed, but usually a defect of the generation: to review.
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return all(rule.covered for rule in self.coverage) and not self.problems


@dataclass(frozen=True)
class FileRef:
    """A file read by a scenario: the rows of a given (rows_file) or the expected rows of a then (expected_file)."""

    scenario: str
    kind: str
    table: str | None
    path: Path


def check_pack(pack: Pack) -> PackReport:
    for table in pack.manifest.data:
        load_rows(pack.data_file(table))

    try:
        scenario_ids = {scenario.id for scenario in Project.load(pack.bigtesty_config).scenarios}
    except BigTestyError as e:
        raise PackError(f"Invalid BigTesty project in the pack: {e}") from e

    unknown = sorted({s for rule in pack.manifest.rules for s in rule.scenarios} - scenario_ids)
    if unknown:
        raise PackError(f"Rules referencing unknown scenarios: {', '.join(unknown)}")

    covered_scenarios = {s for rule in pack.manifest.rules for s in rule.scenarios}
    stale = tuple(
        source.path
        for source in pack.manifest.sources
        if not (pack.root / source.path).is_file() or sha256(pack.root / source.path) != source.sha256
    )
    refs = tuple(_file_refs(pack))

    return PackReport(
        coverage=tuple(RuleCoverage(r.id, r.description, tuple(r.scenarios)) for r in pack.manifest.rules),
        stale_sources=stale,
        scenarios_without_rule=tuple(sorted(scenario_ids - covered_scenarios)),
        problems=(
            *_scenarios_without_when(pack),
            *_expected_in_data(pack, refs),
            *_output_tables_seeded(pack, refs),
        ),
        warnings=(
            *_given_outside_data(pack, refs),
            *_undeclared_data_files(pack),
            *_scenarios_with_several_rules(pack),
            *_no_seedable_environment(pack),
        ),
    )


def _raw_scenarios(pack: Pack) -> Iterator[tuple[str, Path, dict[str, Any]]]:
    """The scenarios as written in the test files, with their ID and their directory: BigTesty resolves the files."""
    config = yaml.safe_load(pack.bigtesty_config.read_text()) or {}
    tests_dir = pack.root / config.get("tests", "tests")
    test_files = sorted(p for p in tests_dir.rglob("*") if p.name.endswith(TEST_FILE_SUFFIXES))

    for test_file in test_files:
        spec = yaml.safe_load(test_file.read_text()) or {}
        for scenario in spec.get("scenarios", []):
            yield f"{test_file.relative_to(tests_dir).as_posix()}::{scenario.get('name')}", test_file.parent, scenario


def _file_refs(pack: Pack) -> Iterator[FileRef]:
    for scenario_id, base, scenario in _raw_scenarios(pack):
        yield from _scenario_refs(scenario_id, base, scenario)


def _scenario_refs(scenario_id: str, base: Path, scenario: dict[str, Any]) -> Iterator[FileRef]:
    blocks = [("given", "rows_file", block) for block in scenario.get("given", [])] + [
        ("then", "expected_file", block) for block in scenario.get("then", [])
    ]
    return (
        FileRef(scenario_id, kind, block.get("table"), (base / block[key]).resolve())
        for kind, key, block in blocks
        if isinstance(block, dict) and block.get(key)
    )


def _data_files(pack: Pack) -> set[Path]:
    return {pack.data_file(table).resolve() for table in pack.manifest.data}


def _relative(pack: Pack, path: Path) -> str:
    return path.relative_to(pack.root).as_posix() if path.is_relative_to(pack.root) else str(path)


def _scenarios_without_when(pack: Pack) -> tuple[str, ...]:
    return tuple(
        f"{scenario_id}: no when, the code under test never runs and the then checks the given rows only"
        for scenario_id, _, scenario in _raw_scenarios(pack)
        if not scenario.get("when")
    )


def _expected_in_data(pack: Pack, refs: tuple[FileRef, ...]) -> tuple[str, ...]:
    data_dir = (pack.root / "data").resolve()
    return tuple(
        f"{ref.scenario}: expected rows read from {_relative(pack, ref.path)}, the data files are seeded into the "
        "environments: write the expected rows in the then"
        for ref in refs
        if ref.kind == "then" and (ref.path.is_relative_to(data_dir) or ref.path in _data_files(pack))
    )


def _output_tables_seeded(pack: Pack, refs: tuple[FileRef, ...]) -> tuple[str, ...]:
    given_tables = {ref.table for ref in refs if ref.kind == "given"}
    then_tables = {ref.table for ref in refs if ref.kind == "then"}
    return tuple(
        f"data of {table}, a table checked by the then and loaded by no given: only the input tables are seeded"
        for table in pack.manifest.data
        if table in then_tables and table not in given_tables
    )


def _given_outside_data(pack: Pack, refs: tuple[FileRef, ...]) -> tuple[str, ...]:
    return tuple(
        f"{ref.scenario}: the given of {ref.table} reads {_relative(pack, ref.path)}, not the data file of the table: "
        "the tests and the seeded environments have different rows"
        for ref in refs
        if ref.kind == "given" and ref.path not in _data_files(pack)
    )


def _undeclared_data_files(pack: Pack) -> tuple[str, ...]:
    data_dir = pack.root / "data"
    files = sorted(p.resolve() for p in data_dir.rglob("*") if p.is_file()) if data_dir.is_dir() else []
    return tuple(
        f"{_relative(pack, path)} is in data/ but in no table of the manifest"
        for path in files
        if path not in _data_files(pack)
    )


def _scenarios_with_several_rules(pack: Pack) -> tuple[str, ...]:
    rules_by_scenario = {
        scenario: [rule.id for rule in pack.manifest.rules if scenario in rule.scenarios]
        for scenario in {s for rule in pack.manifest.rules for s in rule.scenarios}
    }
    return tuple(
        f"{scenario} covers {', '.join(rules)}: one scenario per rule shows which rule fails"
        for scenario, rules in sorted(rules_by_scenario.items())
        if len(rules) > 1
    )


def _no_seedable_environment(pack: Pack) -> tuple[str, ...]:
    if any(env.seedable for env in pack.manifest.environments.values()):
        return ()
    return ("no seedable environment in the manifest: the pack runs the tests, it can't seed an environment",)
