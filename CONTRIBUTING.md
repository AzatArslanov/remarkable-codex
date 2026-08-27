# Contributing

Thanks for helping make reMarkable publishing from Codex safer and more reliable.

## Before you start

Read the [architecture](docs/architecture.md), [contracts](docs/contracts.md), [security model](docs/security.md), and [roadmap](docs/roadmap.md). Changes involving transport, authentication, document formats, or compatibility also need a dated ADR in `docs/adr/` with primary evidence.

Please open an issue before a large refactor. Security vulnerabilities belong in the private process described in [SECURITY.md](SECURITY.md), not a public issue.

## Development setup

Requirements are Python 3.11 or newer and Docker.

```bash
git clone https://github.com/AzatArslanov/remarkable-codex.git
cd remarkable-codex
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Required checks

Run every offline check before opening a pull request:

```bash
ruff check .
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
docker build --pull --tag remarkable-codex-mcp:0.3.0 .
```

Tests must not access the network, Docker state, or a real reMarkable account. Use synthetic Markdown, tokens, identifiers, and responses. Do not commit PDFs, credentials, response captures, SQLite state, or private document content.

## Change workflow

1. Select one unchecked roadmap item and state its acceptance criterion.
2. Add or update a contract test before changing a transport boundary.
3. Keep upload transport behind `Publisher` and cross one architectural boundary at a time.
4. Preserve the publication-only intent boundary, rendered artifacts after failure, sanitized errors, and content-derived idempotency.
5. Update behavior documentation and the roadmap in the same pull request.
6. Report offline results separately from anything observed against a real cloud account or physical device.

## Pull request checklist

- [ ] Public behavior has a regression or contract test.
- [ ] Failures remain classified and contain no secrets, source paths, or document bodies.
- [ ] No credential is accepted through arguments, environment, fixtures, or committed config.
- [ ] No Markdown, PDF, EPUB, or notebook format is silently substituted.
- [ ] Documentation and image version references match the implementation.
- [ ] `ruff`, unit tests, compilation, and Docker build pass locally.
- [ ] Real-account or hardware claims identify the exact route and date observed.

By contributing, you agree that your contribution is licensed under the repository's [MIT License](LICENSE).
