from pathlib import Path

import pytest

from bigseed.agent.adk import build_agent, user_message
from bigseed.agent.base import GenerationRequest, SourceFile, parse_table_option


def _tools(output_dir: Path) -> dict:
    return {tool.__name__: tool for tool in build_agent("gemini-3.1-pro-preview", output_dir).tools}


def test_given_path_outside_of_the_pack_when_write_file_then_refused(tmp_path):
    # WHEN
    result = _tools(tmp_path / "pack")["write_file"]("../outside.json", "[]")

    # THEN
    assert (result, (tmp_path / "outside.json").exists()) == ("refused: ../outside.json is outside of the pack", False)


def test_given_path_in_the_pack_when_write_file_then_written(tmp_path):
    # WHEN
    result = _tools(tmp_path)["write_file"]("data/monitoring/job_failure.json", "[]")

    # THEN
    assert (result, (tmp_path / "data/monitoring/job_failure.json").read_text()) == (
        "written: data/monitoring/job_failure.json",
        "[]",
    )


def test_given_empty_directory_when_check_tool_then_errors_for_the_agent(tmp_path):
    # WHEN / THEN
    assert _tools(tmp_path)["check"]().startswith("errors: No pack in")


def test_given_request_when_user_message_then_schemas_and_inputs_with_their_hash(tmp_path):
    # GIVEN
    request = GenerationRequest(
        sources=(SourceFile(Path("inputs/rules.md"), "- rule", "abc"),),
        schemas={"monitoring.job_failure": [{"name": "jobName", "type": "STRING"}]},
        output_dir=tmp_path,
        pack_name="daily-failures",
    )

    # WHEN
    message = user_message(request)

    # THEN
    assert all(text in message for text in ("Pack name: daily-failures", '"name": "jobName"', "rules.md (sha256 abc)"))


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
