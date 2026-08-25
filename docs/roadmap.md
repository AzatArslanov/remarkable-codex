# Delivery roadmap

## Foundation

- [x] One Markdown text/file MCP contract with deterministic PDF rendering
- [x] Content-addressed PDF artifact preservation
- [x] Persistent credential and successful-upload ledger storage
- [x] Publication-only command contract with no render-only mode

Acceptance: `upload_markdown` accepts exactly one inline/file source, treats file contents as UTF-8 Markdown regardless of suffix, produces the same PDF and idempotency key for identical content and title, and exposes no other MCP operation.

## Simple upload publisher

- [x] Minimal MCP schema for Markdown-to-PDF library upload
- [x] One exact-host simple-upload adapter behind `Publisher`
- [x] Record recognized successes and suppress exact local retries
- [x] Cover mandatory publication, artifact preservation, and secret/content sanitization offline
- [x] Verify two synthetic uploads and one suppressed retry against a real account

Acceptance: two synthetic Markdown sources appear once each as PDFs in the reMarkable library, normally at root; an exact retry causes no second upload; no secret leaks; and every rendered PDF remains local. Verified through the web library on 2026-08-18; physical-device visibility was not directly observed.

## Codex plugin packaging

- [x] Add a validated Codex plugin manifest with a supported `mcpServers` declaration
- [x] Launch the checked-in host MCP control plane relative to the installed plugin root
- [x] Version the plugin and Docker image together across breaking MCP contract changes
- [x] Cover the manifest, bundled launcher, and secret-free MCP configuration with an offline contract test

Acceptance: installing and enabling the local `remarkable-codex` plugin makes exactly one bundled `upload_markdown` MCP tool available in a fresh task. The supported `mcpServers` declaration launches from the installed plugin root without credentials or a separately installed Python console script, requires the matching contract-versioned image, publishes in one call with no mode switches, and preserves idempotent retry and non-retryable-delivery guardrails.

- [x] Prepare the bundled MCP artifact directory without requiring a writable home directory

Sandbox startup acceptance: when the user's home data directory is not writable, the bundled host control plane initializes without touching Docker or the artifact directory. On an actual publication call, a writable process temporary root lets it create the private artifact directory and reach Docker; an explicit `REMARKABLE_ARTIFACT_HOST_DIR` still takes precedence.

- [x] Resolve the bundled publishing tool from Codex's deferred tool registry before reporting it unavailable

Deferred-tool acceptance: in a fresh task where `upload_markdown` is registered under its namespaced MCP name but is not initially visible, the export workflow performs one exact tool search, calls the returned publishing tool, and reports unavailability only when that search has no match.

- [x] Start Docker only for an actual `upload_markdown` call and stop it after the matching response
- [x] Keep the one-shot container input open until the matching publication response is received

Lazy-container acceptance: initializing or continuing a Codex task exposes the same single bundled `upload_markdown` tool without creating a Docker container, touching the credential volume, or requiring the image to be present. A tool call still crosses the explicit publication-intent boundary, stages only its requested file when applicable, runs the exact contract-versioned image under the existing hardening limits, returns the matching MCP response, and leaves no publishing container running after the response or failure.

One-shot response acceptance: after sending the private MCP handshake and publication request, the host keeps container stdin open until it receives the matching response, then closes stdin and waits for clean container removal. A missing response fails closed with `deliveryStatus=unknown` and `retrySafe=false` so callers cannot mistake an unverified outcome for a safe automatic retry.

## Hardening

- [x] Stage arbitrary host-readable Markdown paths through a call-scoped private import directory
- [ ] Characterize endpoint entitlement, size, and rate-limit failures
- [ ] Add sanitized compatibility fixtures for recognized response variants, if observed
- [x] Reject unsupported Unicode glyphs and cover safe PDF links without content leakage
- [x] Add a deterministic long-investigation rendering fixture covering tables and common directional arrows

Acceptance: a representative multi-page investigation with a table and common directional arrows renders deterministically without source rewriting, and unsupported glyphs still fail closed.

File staging acceptance: `filePath` accepts any host-readable regular file without a configured path allowlist; only that file is copied into an ephemeral private directory mounted read-only into the container; the original host path and document body do not enter command arguments, environment variables, diagnostics, or failure results; and staged content is removed after the matching MCP response or call exit. Final-component symlinks, non-regular files, and sources over 10 MB fail before container publication.
