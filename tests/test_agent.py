from pathlib import Path

import pytest
from google.cloud import bigquery

from bigseed.agent.adk import PackFile, _api_error_message, _describe_response, build_agent, user_message
from bigseed.agent.base import (
    GenerationRequest,
    SourceFile,
    environment_from_tables,
    location_of,
    parse_table_option,
)
from bigseed.errors import BigSeedError


def _tools(output_dir: Path) -> dict:
    return {tool.__name__: tool for tool in build_agent("gemini-3.1-pro-preview", output_dir).tools}


def test_given_path_outside_of_the_pack_when_write_files_then_refused(tmp_path):
    # WHEN
    result = _tools(tmp_path / "pack")["write_files"]([PackFile(path="../outside.json", content="[]")])

    # THEN
    assert (result, (tmp_path / "outside.json").exists()) == ("refused: ../outside.json is outside of the pack", False)


def test_given_several_files_when_write_files_then_all_written_in_one_call(tmp_path):
    # GIVEN
    files = [PackFile(path="data/monitoring/job_failure.json", content="[]"), PackFile(path="pack.yaml", content="")]

    # WHEN
    result = _tools(tmp_path)["write_files"](files)

    # THEN
    assert (result, (tmp_path / "data/monitoring/job_failure.json").read_text()) == (
        "written: data/monitoring/job_failure.json\nwritten: pack.yaml",
        "[]",
    )


def test_given_empty_directory_when_check_tool_then_error_for_the_agent(tmp_path):
    # WHEN / THEN
    assert _tools(tmp_path)["check"]().startswith("error: No pack in")


def test_given_pack_with_expected_rows_in_data_when_check_tool_then_what_to_fix(pack_dir):
    # GIVEN
    (pack_dir / "data/monitoring/daily_failures.json").write_text("[]")

    # WHEN
    result = _tools(pack_dir)["check"]()

    # THEN
    assert result == ("to fix:\n- data/monitoring/daily_failures.json is in data/ but in no table of the manifest")


def test_given_example_pack_when_check_tool_then_ok():
    # GIVEN
    from conftest import EXAMPLE_PACK

    # WHEN / THEN
    assert _tools(EXAMPLE_PACK)["check"]() == "ok"


def test_given_request_when_user_message_then_schemas_and_inputs_with_their_hash(tmp_path):
    # GIVEN
    request = GenerationRequest(
        sources=(SourceFile(Path("inputs/rules.md"), "- rule", "abc"),),
        schemas={"monitoring.job_failure": [{"name": "jobName", "type": "STRING"}]},
        output_dir=tmp_path,
        pack_name="daily-failures",
        location="EU",
    )

    # WHEN
    message = user_message(request)

    # THEN
    assert all(
        text in message
        for text in (
            "Pack name: daily-failures",
            "location of the datasets: EU",
            '"name": "jobName"',
            "rules.md (sha256 abc)",
        )
    )


@pytest.mark.parametrize(
    ("option", "expected"),
    [
        # --- Case 1: the pack table is the dataset and table of the source ---
        ("my-project.monitoring.job_failure", ("monitoring.job_failure", "my-project.monitoring.job_failure")),
        # --- Case 2: the schema read from another dataset ---
        (
            "monitoring.job_failure=my-project.monitoring_uat.job_failure",
            ("monitoring.job_failure", "my-project.monitoring_uat.job_failure"),
        ),
    ],
)
def test_given_table_option_when_parse_then_pack_table_and_source(option, expected):
    # WHEN / THEN
    assert parse_table_option(option) == expected


def test_given_tables_of_one_project_when_environment_from_tables_then_project_and_datasets():
    # GIVEN
    tables = {
        "monitoring.job_failure": "my-uat.monitoring_uat.job_failure",
        "monitoring.daily_failures": "my-uat.monitoring_uat.daily_failures",
        "ref.feature": "my-uat.ref_uat.feature",
    }

    # WHEN / THEN
    assert environment_from_tables(tables) == {
        "project": "my-uat",
        "datasets": {"monitoring": "monitoring_uat", "ref": "ref_uat"},
    }


@pytest.mark.parametrize(
    ("tables", "error_message"),
    [
        # --- Case 1: tables of two projects ---
        ({"a.t1": "p1.a.t1", "b.t2": "p2.b.t2"}, "found p1, p2"),
        # --- Case 2: a dataset of the pack read from two datasets ---
        ({"a.t1": "p1.a_uat.t1", "a.t2": "p1.a_dev.t2"}, "one source dataset per dataset"),
    ],
)
def test_given_ambiguous_tables_when_environment_from_tables_then_error(tables, error_message):
    # WHEN / THEN
    with pytest.raises(BigSeedError, match=error_message):
        environment_from_tables(tables)


@pytest.mark.parametrize(
    ("code", "status", "expected_start"),
    [
        # --- Case 1: quota exhausted, even after the retries ---
        (429, "RESOURCE_EXHAUSTED", "The quota of gemini-x is exhausted (429), even after 6 attempts"),
        # --- Case 2: model unknown in the project or the location ---
        (404, "NOT_FOUND", "Unknown model gemini-x in this project and location (404)"),
        # --- Case 3: any other error of the model ---
        (403, "PERMISSION_DENIED", "The model gemini-x failed (403 PERMISSION_DENIED)"),
    ],
)
def test_given_api_error_when_api_error_message_then_clear_message(code, status, expected_start):
    # GIVEN
    from google.genai import errors

    error = errors.ClientError(code, {"error": {"code": code, "message": "details", "status": status}})

    # WHEN
    message = _api_error_message("gemini-x", error)

    # THEN
    assert (message.startswith(expected_start), message.endswith("details")) == (True, True)


@pytest.mark.parametrize(
    ("tool", "response", "expected"),
    [
        # --- Case 1: the files written, the first one shown ---
        ("write_files", {"result": "written: a\nwritten: b"}, "   12.0s  write_files    <- written: a (+1 lines)"),
        # --- Case 2: every line of the check, what the agent has to fix ---
        ("check", {"result": "to fix:\n- R1"}, "   12.0s  check          <- to fix:\n   12.0s  check          <- - R1"),
    ],
)
def test_given_tool_response_when_describe_response_then_progress_lines(tool, response, expected):
    # WHEN / THEN
    assert _describe_response(12.0, tool, response) == expected


@pytest.mark.parametrize(
    ("locations", "expected"),
    [
        # --- Case 1: every table in one location ---
        (["EU", "EU"], "EU"),
        # --- Case 2: a single table ---
        (["us-central1"], "us-central1"),
    ],
)
def test_given_tables_of_one_location_when_location_of_then_the_location(locations, expected):
    # GIVEN
    tables = {f"d.t{i}": _table(f"p.d.t{i}", location) for i, location in enumerate(locations)}

    # WHEN / THEN
    assert location_of(tables) == expected


def test_given_tables_of_two_locations_when_location_of_then_error():
    # GIVEN
    tables = {"a.t1": _table("p.a.t1", "EU"), "b.t2": _table("p.b.t2", "US")}

    # WHEN / THEN
    with pytest.raises(BigSeedError, match="one location, found: EU, US"):
        location_of(tables)


def _table(table_id: str, location: str) -> bigquery.Table:
    table = bigquery.Table(table_id)
    table._properties["location"] = location
    return table
