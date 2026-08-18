# Markdown Publisher for reMarkable

A local Codex plugin that accepts Markdown text or a UTF-8 text file, renders it as a paper-friendly PDF, and uploads that PDF to the reMarkable library. Uploads normally land in the library root.

Markdown is the only source contract and PDF is an internal artifact. There is no PDF import, format selection, artifact reuse input, notebook conversion, or silent format downgrade. Dry-run remains the default.

## Install and build

Requirements: Docker and Python 3.11 or newer.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
remarkable-publish-mcp-docker build
```

The launcher mounts one writable artifact directory, approved read-only Markdown import roots, and a protected named volume for the device credential and successful-upload ledger.

## Operations

```bash
remarkable-publish-mcp-docker status
remarkable-publish-mcp-docker auth login
remarkable-publish-mcp-docker auth status
remarkable-publish-mcp-docker auth revoke
remarkable-publish-mcp-docker serve
```

The MCP exposes only `upload_markdown`. It accepts exactly one of `markdownText` or `filePath`, plus `title`, `dryRun=true`, and `confirmUpload=false`. A regular file is decoded as UTF-8 and treated as Markdown regardless of its extension. HTTP(S) and mailto Markdown links become PDF links. Input containing glyphs unavailable in the embedded fonts is rejected instead of producing a silently corrupted PDF. The tool renders and preserves a content-addressed PDF before any upload.

A live call requires `confirmUpload=true`, `REMARKABLE_BACKEND=simple-upload`, and `REMARKABLE_EXPERIMENTAL_SIMPLE_UPLOAD=1`. The observed endpoint normally imports into the library root.

Only non-secret runtime options may be passed in the environment. Device credentials remain in the protected volume and exchanged user tokens remain in memory.

## Idempotency

The idempotency key is derived from the rendered PDF SHA-256 and title. A state-volume lock serializes live uploads, and after a recognized successful response the local SQLite ledger suppresses an exact retry without another upload. This is installation-local protection: it cannot detect uploads made by another installation or after ledger loss. If delivery is confirmed but the ledger cannot record it, the result says that delivery is confirmed and that retrying is unsafe.

## Development and verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests scripts
docker build --pull --tag remarkable-codex-mcp:0.2.0 .
```

Unit tests are offline. A real-account test requires explicit confirmation and synthetic Markdown content. No generated PDF, credential, response capture, or state database belongs in version control.
