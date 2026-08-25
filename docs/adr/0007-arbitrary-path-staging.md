# ADR 0007: Stage one arbitrary host file per MCP request

Date checked: 2026-08-19

Call lifetime amended by ADR 0009 on 2026-08-21.

## Status

Accepted

## Context

Agents commonly create reports outside a preconfigured import directory. Requiring an approved root made the public `filePath` input unreliable and encouraged agents to duplicate large documents into `markdownText`. Mounting a workspace, home directory, or host root would make arbitrary paths readable but would also expose unrelated files and credentials to the container.

## Decision

Keep `filePath` in the public `upload_markdown` schema and accept any regular file readable by the host launcher. The standard-library launcher acts as a narrow stdio broker. For each valid file call it securely reads only the requested file, copies at most 10 MB into a private call-scoped staging directory, substitutes an opaque `/imports/0` path in the forwarded JSON-RPC request, and mounts only that staging directory read-only into the container.

Reject final-component symlinks, non-regular paths, unreadable files, and oversized sources locally with sanitized application failures. Remove a staged file after its matching JSON-RPC response and remove the temporary directory at call exit. Preserve the container's `/imports/0` allowlist as defense in depth. Do not put original host paths or document bodies in Docker arguments, environment variables, diagnostics, or failure results.

## Consequences

Agents can use a stable `filePath` input without import-root setup, subject to the operating system permissions of the launcher. The container receives no broad host mount and cannot use a crafted tool argument to read the credential volume. The host broker becomes part of the MCP transport boundary and requires protocol-level contract tests for rewriting, cleanup, and local failures.
