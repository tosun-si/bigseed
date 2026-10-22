"""
The pack generator with Google ADK (pip install "bigseed[agent]"): an LlmAgent writing the files of the pack with
tools restricted to the output directory, and checking the pack before finishing.
"""

import asyncio
import json
from pathlib import Path

from bigseed.agent.base import GenerationRequest
from bigseed.agent.prompts import INSTRUCTION
from bigseed.check import check_pack
from bigseed.errors import BigSeedError
from bigseed.pack import load_pack

DEFAULT_MODEL = "gemini-2.5-pro"
APP_NAME = "bigseed"


class AdkPackGenerator:
    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model

    def generate(self, request: GenerationRequest) -> None:
        asyncio.run(self._generate(request))

    async def _generate(self, request: GenerationRequest) -> None:
        from google.adk.runners import InMemoryRunner  # noqa: PLC0415, optional dependency
        from google.genai import types  # noqa: PLC0415

        runner = InMemoryRunner(agent=build_agent(self.model, request.output_dir), app_name=APP_NAME)
        session = await runner.session_service.create_session(app_name=APP_NAME, user_id="bigseed")
        message = types.Content(role="user", parts=[types.Part(text=user_message(request))])

        async for _ in runner.run_async(user_id="bigseed", session_id=session.id, new_message=message):
            pass


def build_agent(model: str, output_dir: Path):  # type: ignore[no-untyped-def]
    from google.adk.agents import LlmAgent  # noqa: PLC0415

    root = output_dir.resolve()

    def write_file(path: str, content: str) -> str:
        """Writes a file of the pack, path relative to the pack directory (e.g. data/monitoring/job_failure.json)."""
        target = (root / path).resolve()
        if not target.is_relative_to(root):
            return f"refused: {path} is outside of the pack"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"written: {path}"

    def check() -> str:
        """Checks the pack: manifest, data files, BigTesty files, coverage of the rules. Returns 'ok' or the errors."""
        try:
            report = check_pack(load_pack(root))
        except BigSeedError as e:
            return f"errors: {e}"
        uncovered = [rule.rule_id for rule in report.coverage if not rule.covered]
        return "ok" if not uncovered else f"rules without scenario: {', '.join(uncovered)}"

    return LlmAgent(
        name="bigseed_pack_generator",
        model=model,
        instruction=INSTRUCTION,
        tools=[write_file, check],
    )


def user_message(request: GenerationRequest) -> str:
    sources = "\n\n".join(
        f"### {source.path.name} (sha256 {source.sha256})\n```\n{source.content}\n```" for source in request.sources
    )
    return (
        f"Pack name: {request.pack_name}\n\n"
        f"BigQuery schemas of the tables:\n```json\n{json.dumps(request.schemas, indent=2)}\n```\n\n"
        "Inputs, already copied in the inputs/ directory of the pack: reference them as inputs/<file name>.\n\n"
        f"{sources}"
    )
