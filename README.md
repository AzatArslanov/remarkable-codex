# Markdown Publisher for reMarkable

A local Codex plugin that accepts Markdown text or a UTF-8 text file, renders it as a paper-friendly PDF, and uploads that PDF to the reMarkable library. Uploads normally land in the library root.

Markdown is the only source contract and PDF is an internal artifact. There is no PDF import, format selection, artifact reuse input, notebook conversion, silent format downgrade, or render-only mode. Every accepted upload command attempts publication.

The plugin bundles the `upload_markdown` stdio MCP declaration. Codex launches a standard-library host MCP control plane from the installed plugin directory, so no separately registered endpoint or Python console-script installation is required. Initialization and tool discovery stay on the host and do not start Docker. An actual `upload_markdown` call starts the exact contract-versioned `remarkable-codex-mcp:0.3.0` image, forwards one call through an internal MCP handshake, keeps container stdin open until the matching response arrives, and then waits for the `--rm` container to exit. Docker and the local image are therefore publication prerequisites, not task-start prerequisites. An older image must not be reused with this plugin version.

By default, preserved PDFs are written under the process temporary root so publication can run inside Codex's workspace sandbox; operators may set `REMARKABLE_ARTIFACT_HOST_DIR` to another writable directory. The artifact directory and protected state volume are touched only after an actual publication call.

Codex may keep plugin MCP tools in its deferred registry. The bundled export skill performs one exact search for `upload_markdown` when the tool is not initially visible, then calls the returned namespaced tool. It reports the server unavailable only when that exact search has no match.

## Install and build

Requirements: Docker and Python 3.11 or newer.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
remarkable-publish-mcp-docker build
```

The editable install is needed for the operator commands below, but the installed Codex plugin starts its bundled MCP wrapper directly from the plugin package.

For each publication call, the launcher mounts one writable artifact directory, one private call-scoped staging directory read-only, and a protected named volume for the device credential and successful-upload ledger. For `filePath` calls, the host broker copies only the requested file into staging and removes it after the matching MCP response or container exit. It never mounts a workspace, home directory, or host root into the container. Invalid local file inputs fail before Docker starts.

## Operations

```bash
remarkable-publish-mcp-docker status
remarkable-publish-mcp-docker auth login
remarkable-publish-mcp-docker auth status
remarkable-publish-mcp-docker auth revoke
remarkable-publish-mcp-docker serve
```

`serve` runs the lightweight host stdio control plane. It can initialize and list tools without Docker access; Docker is first contacted by an `upload_markdown` call.

The MCP exposes only `upload_markdown`. It accepts exactly one of `markdownText` or `filePath`, plus `title`. `filePath` may identify any host-readable regular file; no import-root configuration is required. Final-component symlinks, non-regular files, and inputs over 10 MB fail locally before the request reaches the container. A regular file is decoded as UTF-8 and treated as Markdown regardless of its extension. HTTP(S) and mailto Markdown links become PDF links. Common directional arrows use a deterministic symbol-font fallback; input containing glyphs unavailable in the renderer font set is rejected instead of producing a silently corrupted PDF. The tool renders and preserves a content-addressed PDF, then attempts publication in the same call.

Calling `upload_markdown` or the CLI `upload` command is explicit publication intent. There are no mode, preview, confirmation, backend-selection, or experimental opt-in switches. A stored device credential is still required. The observed endpoint normally imports into the library root.

Only non-secret runtime options may be passed in the environment. Device credentials remain in the protected volume and exchanged user tokens remain in memory.

## Idempotency

The idempotency key is derived from the rendered PDF SHA-256 and title. A state-volume lock serializes live uploads, and after a recognized successful response the local SQLite ledger suppresses an exact retry without another upload. This is installation-local protection: it cannot detect uploads made by another installation or after ledger loss. If delivery is confirmed but the ledger cannot record it, the result says that delivery is confirmed and that retrying is unsafe.

## Development and verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests scripts
docker build --pull --tag remarkable-codex-mcp:0.3.0 .
```

Unit tests are offline. A real-account test requires explicit confirmation and synthetic Markdown content. No generated PDF, credential, response capture, or state database belongs in version control.
