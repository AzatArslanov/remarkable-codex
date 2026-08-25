# Agent working agreement

## Mission

Build a reliable Codex plugin that turns investigation results and summaries into paper-friendly documents and uploads them to the reMarkable library.

The user-facing promise is: **previewable, idempotent publishing with no secret leakage or silent format downgrade**.

## Read first

Before changing behavior, read:

1. `README.md`
2. `docs/architecture.md`
3. `docs/contracts.md`
4. `docs/security.md`
5. `docs/roadmap.md`
6. `skills/export-summary-to-remarkable/SKILL.md` when changing the agent workflow

## Non-negotiable constraints

- Do not claim there is an official reMarkable cloud publishing API unless reMarkable publishes one and the claim is linked to primary documentation.
- Keep the upload transport behind `Publisher`.
- Never put credentials in command arguments, logs, fixtures, generated documents, or committed config.
- Upload only after explicit user intent. Invoking the publication-only MCP tool or CLI upload command is that intent boundary; do not add a render-only or dry-run mode.
- Do not silently convert `notebook` to PDF or EPUB.
- Preserve the rendered artifact after transport failure.
- Emit exactly one machine-readable JSON result on stdout; diagnostics go to stderr.
- Keep publish retries idempotent through a content-derived idempotency key.
- Unit tests must not access the network or a real account.

## Change workflow

1. Pick one unchecked roadmap item and state its acceptance criterion.
2. Add or update a contract test before transport implementation.
3. Make the smallest change that crosses one architectural boundary at a time.
4. Run all local checks documented in `README.md`.
5. Update docs and the roadmap in the same change when behavior or assumptions move.
6. Report what remains unverified against real hardware/cloud separately from automated results.

## Definition of done

A change is done when its public behavior is tested, failures are classified, secret handling is reviewed, docs match reality, publication intent remains explicit, and no generated artifact or credential is committed.

## Repository map

- `.codex-plugin/`: Codex plugin manifest
- `skills/`: agent-facing workflow and backend selection guidance
- `src/remarkable_publish/`: CLI, application service, domain types, and adapters
- `tests/`: offline contract and unit tests
- `docs/`: decisions, contracts, security model, and delivery roadmap
- `scripts/`: repository maintenance helpers only; production logic belongs in `src/`

## Decision policy

Record choices that affect transports, authentication, document formats, or compatibility as an ADR under `docs/adr/`. Prefer evidence from reMarkable documentation or the source repository of a third-party tool. Include the date checked because the integration landscape changes.
