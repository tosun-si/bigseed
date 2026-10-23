import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.cloud import bigquery

from bigseed import __version__
from bigseed.check import check_pack
from bigseed.errors import BigSeedError
from bigseed.pack import load_pack
from bigseed.seed import seed, seed_plan

app = typer.Typer(
    help="Coherent BigQuery test datasets and scenarios, generated from the business rules, run with BigTesty.",
    no_args_is_help=True,
)

PackOption = Annotated[Path, typer.Option("--pack", "-p", help="Directory of the pack.")]


@app.command("generate", help="Generate a pack from the inputs with the agent (pip install 'bigseed[agent]').")
def generate_command(
    inputs: Annotated[list[Path], typer.Argument(help="SQL, Python, Java or Markdown files holding the rules.")],
    table: Annotated[
        list[str],
        typer.Option(
            "--table",
            "-t",
            help="Table read or written by the rules, project.dataset.table, or dataset.table=project.dataset.table to "
            "read the schema of another dataset (e.g. monitoring.job_failure=my-project.monitoring_uat.job_failure).",
        ),
    ],
    output: Annotated[Path, typer.Option("--output", "-o", help="Directory of the new pack.")],
    name: Annotated[str | None, typer.Option(help="Name of the pack, the output directory name by default.")] = None,
    model: Annotated[str | None, typer.Option(help="Model of the agent.")] = None,
) -> None:
    from bigseed.agent.adk import DEFAULT_MODEL, adk_generator  # noqa: PLC0415, optional dependency
    from bigseed.agent.base import GenerationRequest, parse_table_option, read_schemas, read_sources  # noqa: PLC0415

    with _handle_errors():
        if output.exists() and any(output.iterdir()):
            raise BigSeedError(f"{output} is not empty: generate a new pack in a new directory")

        # The inputs are part of the pack: its sources and their hashes stay checkable after the generation.
        (output / "inputs").mkdir(parents=True, exist_ok=True)
        copies = [Path(shutil.copy(path, output / "inputs" / path.name)) for path in inputs]

        request = GenerationRequest(
            sources=read_sources(copies),
            schemas=read_schemas(bigquery.Client(), dict(map(parse_table_option, table))),
            output_dir=output,
            pack_name=name or output.name,
        )
        adk_generator(model or DEFAULT_MODEL)(request)

    typer.echo(f"Pack written in {output}: review it, then run `bigseed check -p {output}` and `bigtesty test`.")


@app.command("check", help="Check a pack: manifest, data files, BigTesty files, coverage of the rules.")
def check_command(pack: PackOption = Path(".")) -> None:
    with _handle_errors():
        report = check_pack(load_pack(pack))

    for rule in report.coverage:
        mark = "covered  " if rule.covered else "UNCOVERED"
        typer.echo(f"{mark}  {rule.rule_id}  {rule.description}")
        for scenario in rule.scenarios:
            typer.echo(f"             {scenario}")
    for scenario in report.scenarios_without_rule:
        typer.echo(f"no rule    {scenario}")
    for source in report.stale_sources:
        typer.secho(f"stale      {source} changed since the generation", fg=typer.colors.YELLOW)

    if any(not rule.covered for rule in report.coverage):
        raise typer.Exit(code=1)


@app.command("seed", help="Replace the rows of the tables of an environment by the rows of the pack.")
def seed_command(
    environment: Annotated[str, typer.Argument(help="Environment declared in pack.yaml, e.g. uat.")],
    pack: PackOption = Path("."),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show the tables and rows, seed nothing.")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Don't ask for confirmation.")] = False,
) -> None:
    with _handle_errors():
        loaded = load_pack(pack)
        steps = seed_plan(loaded, environment)

        for step in steps:
            typer.echo(f"{step.target}  <- {step.rows} rows ({step.table})")
        if dry_run:
            return
        if not yes:
            typer.confirm(
                f"Replace the rows of these {len(steps)} tables by the pack {loaded.manifest.name} "
                f"v{loaded.manifest.version}?",
                abort=True,
            )

        seed(loaded, environment, bigquery.Client(project=loaded.manifest.environments[environment].project))

    typer.echo(f"Seeded {environment} with {loaded.manifest.name} v{loaded.manifest.version}")


@app.command("version", help="Show the BigSeed version.")
def version_command() -> None:
    typer.echo(__version__)


@contextmanager
def _handle_errors() -> Iterator[None]:
    try:
        yield
    except BigSeedError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from e
    except (DefaultCredentialsError, RefreshError) as e:
        typer.secho(f"GCP authentication error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from e
