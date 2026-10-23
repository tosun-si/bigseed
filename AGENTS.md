<!-- agents-md-manager:start — managed section, do not edit by hand -->
# BigSeed — Project context

> Project-level context for AI coding agents (GitHub Copilot, Claude Code,
> Cursor…). **Conventions live in the referenced skills; this file only holds what
> is NOT in a skill and NOT derivable from code.**

## Identity

- **Domain**: open-source data tooling (BigQuery testing)
- **Project**: BigSeed
- **Purpose**: generate coherent BigQuery test datasets and Given / When / Then scenarios from the business rules of
  the code (a "pack"), seed an environment with them and run them with BigTesty
- **Repo layout**: standalone

## Conventions — source of truth (referenced, NOT copied)

This repo follows these catalog skills. Change a convention there, not here:

- `commit-open-source` — commit messages, no Claude attribution
- `tag-opensource` — release tags, PyPI Trusted Publishing, GitHub Releases as changelog
- `python-uv-direnv` — uv venv and direnv activation
- `unit-test-given-when-then` — test naming and structure

## Project specifics (not in any skill, not derivable from code)

- **Jira**: none (GitHub issues, `tosun-si/bigseed` once published)
- **GCP projects**: integration tests and Vertex AI on `gb-poc-373711`; locally, set
  `GOOGLE_CLOUD_QUOTA_PROJECT` (the ADC have no quota project, Vertex AI calls fail without it)
- **Service accounts**: none yet
- **Non-obvious decisions**:
  - Functional style with the standard library only: pure functions, frozen dataclasses, comprehensions, `Callable`
    aliases over behavior classes; side effects at the edges. No FP library.
  - BigTesty is the execution engine (`bigtesty.api`): never reimplement running or asserting scenarios here.
  - The oracle rule: expected rows come from the rules and specs, never from the SQL under test.
  - A human approves every pack; the agent never publishes. Environments are an allowlist (`seedable: false`), the
    agent reads schemas only, never rows.
  - Open source (Apache 2), self-hosted in the user's project; no SaaS.
<!-- agents-md-manager:end -->

<!-- Free zone — add durable, project-specific notes below. -->
<!-- Keep code-derivable facts (structure, deps, schedule) OUT. -->
