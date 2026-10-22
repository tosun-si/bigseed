"""
Checks a pack before its approval: the manifest, the data files, the BigTesty project, the coverage of the rules by
the scenarios, and the inputs changed since the generation. No call to BigQuery: the scenarios are run by BigTesty.
"""

from dataclasses import dataclass, field

from bigtesty.api import Project
from bigtesty.exceptions import BigTestyError

from bigseed.errors import PackError
from bigseed.pack import Pack, load_rows, sha256


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
    scenarios_without_rule: tuple[str, ...] = field(default=())


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

    return PackReport(
        coverage=tuple(RuleCoverage(r.id, r.description, tuple(r.scenarios)) for r in pack.manifest.rules),
        stale_sources=stale,
        scenarios_without_rule=tuple(sorted(scenario_ids - covered_scenarios)),
    )
