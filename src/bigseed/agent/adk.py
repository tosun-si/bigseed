"""
The pack generator with Google ADK (pip install "bigseed[agent]"): an LlmAgent writing the files of the pack with
tools restricted to the output directory, and checking the pack before finishing.
"""

import asyncio
import json
import logging
import time
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from bigseed.agent.base import GenerationRequest, GenerationStats, PackGenerator
from bigseed.agent.prompts import INSTRUCTION
from bigseed.check import check_pack
from bigseed.errors import BigSeedError, GenerationError
from bigseed.pack import load_pack

DEFAULT_MODEL = "gemini-3.8-flash"
APP_NAME = "bigseed"
# The calls refused by the quota (429) or failed on the server are retried with a backoff.
RETRY_ATTEMPTS = 6

# Receives a line for each call of the model and each call of a tool, for --verbose.
ProgressListener = Callable[[str], None]


class PackFile(BaseModel):
    path: str
    content: str


@dataclass(frozen=True)
class Step:
    """An event of the agent: a response of the model, with the tools it calls."""

    seconds: float
    prompt_tokens: int
    output_tokens: int
    thinking_tokens: int
    tool_calls: tuple[str, ...]


def adk_generator(model: str = DEFAULT_MODEL, on_progress: ProgressListener | None = None) -> PackGenerator:
    """The pack generator with an ADK agent on `model`."""
    return lambda request: asyncio.run(_generate(model, request, on_progress or (lambda _: None)))


async def _generate(model: str, request: GenerationRequest, on_progress: ProgressListener) -> GenerationStats:
    from google.adk.runners import InMemoryRunner  # noqa: PLC0415, optional dependency
    from google.genai import errors, types  # noqa: PLC0415

    runner = InMemoryRunner(agent=build_agent(model, request.output_dir), app_name=APP_NAME)
    session = await runner.session_service.create_session(app_name=APP_NAME, user_id="bigseed")
    message = types.Content(role="user", parts=[types.Part(text=user_message(request))])

    # The errors of the model are raised as a GenerationError: ADK logging them with their traceback is noise.
    logging.getLogger("google_adk").setLevel(logging.CRITICAL)
    warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\]")

    start = time.monotonic()
    steps: list[Step] = []
    try:
        async for event in runner.run_async(user_id="bigseed", session_id=session.id, new_message=message):
            seconds = time.monotonic() - start
            for response in event.get_function_responses():
                on_progress(_describe_response(seconds, response.name or "", response.response))
            if event.usage_metadata is not None:
                step = _step(event, seconds)
                steps.append(step)
                on_progress(_describe(step))
    except errors.APIError as e:
        raise GenerationError(_api_error_message(model, e)) from e

    return GenerationStats(
        model_calls=len(steps),
        tool_calls=sum(len(step.tool_calls) for step in steps),
        prompt_tokens=sum(step.prompt_tokens for step in steps),
        output_tokens=sum(step.output_tokens for step in steps),
        thinking_tokens=sum(step.thinking_tokens for step in steps),
        seconds=time.monotonic() - start,
    )


def _step(event: Any, seconds: float) -> Step:
    usage = event.usage_metadata
    return Step(
        seconds=seconds,
        prompt_tokens=usage.prompt_token_count or 0,
        output_tokens=usage.candidates_token_count or 0,
        thinking_tokens=usage.thoughts_token_count or 0,
        tool_calls=tuple(call.name for call in event.get_function_calls()),
    )


def _describe(step: Step) -> str:
    tools = ", ".join(step.tool_calls) or "answer"
    return (
        f"{step.seconds:7.1f}s  model -> {tools:<20}  {step.prompt_tokens:>7} in  {step.output_tokens:>6} out  "
        f"{step.thinking_tokens:>6} thinking"
    )


def _describe_response(seconds: float, tool: str, response: Any) -> str:
    # A function tool returning a str is wrapped by ADK in {"result": ...}.
    result = str(response.get("result", response) if isinstance(response, dict) else response)
    lines = result.splitlines() or [""]
    more = f" (+{len(lines) - 1} lines)" if len(lines) > 1 and tool == "write_files" else ""
    shown = lines[:1] if tool == "write_files" else lines
    return "\n".join(f"{seconds:7.1f}s  {tool:<14} <- {line}" for line in shown) + more


def _api_error_message(model: str, error: Any) -> str:
    if error.code == 429:
        return (
            f"The quota of {model} is exhausted (429), even after {RETRY_ATTEMPTS} attempts: retry later, use a "
            f"lighter model (--model), or ask for a higher tokens per minute quota. {error.message}"
        )
    if error.code == 404:
        return f"Unknown model {model} in this project and location (404): {error.message}"
    return f"The model {model} failed ({error.code} {error.status}): {error.message}"


def build_agent(model: str, output_dir: Path):  # type: ignore[no-untyped-def]
    from google.adk.agents import LlmAgent  # noqa: PLC0415
    from google.adk.models import Gemini  # noqa: PLC0415
    from google.genai import types  # noqa: PLC0415

    root = output_dir.resolve()

    def write_files(files: list[PackFile]) -> str:
        """
        Writes files of the pack, all of them in one call when possible. Each path is relative to the pack directory
        (e.g. data/monitoring/job_failure.json), an existing file is replaced.
        """
        return "\n".join(_write(root, file) for file in files)

    def check() -> str:
        """Checks the pack: manifest, data files, BigTesty files, coverage of the rules. Returns 'ok' or what to fix."""
        try:
            report = check_pack(load_pack(root))
        except BigSeedError as e:
            return f"error: {e}"
        to_fix = [
            *report.problems,
            *(f"rule without scenario: {rule.rule_id}" for rule in report.coverage if not rule.covered),
            *(f"scenario without rule: {scenario}" for scenario in report.scenarios_without_rule),
            *report.warnings,
        ]
        return "ok" if not to_fix else "to fix:\n" + "\n".join(f"- {line}" for line in to_fix)

    return LlmAgent(
        name="bigseed_pack_generator",
        model=Gemini(model=model, retry_options=types.HttpRetryOptions(attempts=RETRY_ATTEMPTS, initial_delay=2)),
        instruction=INSTRUCTION,
        tools=[write_files, check],
    )


def _write(root: Path, file: PackFile) -> str:
    target = (root / file.path).resolve()
    if not target.is_relative_to(root):
        return f"refused: {file.path} is outside of the pack"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(file.content)
    return f"written: {file.path}"


def user_message(request: GenerationRequest) -> str:
    sources = "\n\n".join(
        f"### {source.path.name} (sha256 {source.sha256})\n```\n{source.content}\n```" for source in request.sources
    )
    return (
        f"Pack name: {request.pack_name}\n\n"
        f"BigQuery location of the datasets: {request.location}\n\n"
        f"BigQuery schemas of the tables:\n```json\n{json.dumps(request.schemas, indent=2)}\n```\n\n"
        f"Environments of the manifest:\n```json\n{json.dumps(request.environments, indent=2)}\n```\n\n"
        "Inputs, already copied in the inputs/ directory of the pack: reference them as inputs/<file name>.\n\n"
        f"{sources}"
    )
