# Delivery roadmap

## Foundation

- [x] One Markdown text/file MCP contract with deterministic PDF rendering
- [x] Content-addressed PDF artifact preservation
- [x] Persistent credential and successful-upload ledger storage
- [x] Dry-run default and explicit live confirmation gate

Acceptance: `upload_markdown` accepts exactly one inline/file source, treats file contents as UTF-8 Markdown regardless of suffix, produces the same PDF and idempotency key for identical content and title, and exposes no other MCP operation.

## Simple upload publisher

- [x] Minimal MCP schema for Markdown-to-PDF library upload
- [x] One exact-host simple-upload adapter behind `Publisher`
- [x] Record recognized successes and suppress exact local retries
- [x] Cover dry-run isolation, artifact preservation, and secret/content sanitization offline
- [x] Verify two synthetic uploads and one suppressed retry against a real account

Acceptance: two synthetic Markdown sources appear once each as PDFs in the reMarkable library, normally at root; an exact retry causes no second upload; no secret leaks; and every rendered PDF remains local. Verified through the web library on 2026-08-18; physical-device visibility was not directly observed.

## Hardening

- [ ] Characterize endpoint entitlement, size, and rate-limit failures
- [ ] Add sanitized compatibility fixtures for recognized response variants, if observed
- [x] Reject unsupported Unicode glyphs and cover safe PDF links without content leakage
- [ ] Add golden rendering fixtures for tables and long investigations
