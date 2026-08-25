# ADR 0006: Narrow symbol fallback for investigation typography

Date checked: 2026-08-19

## Status

Accepted

## Context

Agent-authored investigations commonly contain directional arrows such as `→`. The primary bundled Vera fonts do not contain these glyphs, so otherwise valid reports failed before PDF creation. Rewriting arrows as ASCII changes user content and conflicts with fail-closed rendering.

## Decision

Keep Vera as the body, bold, and monospace font family, and render only `←`, `→`, `↔`, `⇒`, and `⇔` through ReportLab's deterministic PDF Symbol font mapping. Preserve each Unicode character in the extracted PDF text. Continue rejecting every character absent from this explicit renderer font set, reporting code points without source excerpts.

The `filePath` isolation boundary is governed separately by ADR 0007.

## Consequences

Common workflow notation renders without content mutation, while the compatibility surface remains small and covered by a multi-page fixture. Broader scripts and symbols still fail closed. No host directory is newly mounted, and no transport or authentication behavior changes.
