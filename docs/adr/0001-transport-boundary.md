# ADR 0001: Isolate the upload transport

- Status: accepted
- Date checked: 2026-08-18

## Context

reMarkable publishes developer information and user documentation for importing through supported applications, the web application, and USB. No supported public cloud-upload API contract was found.

## Decision

The application core depends on a repository-owned `Publisher` protocol. Dry-run is the default backend. The observed simple-upload adapter is experimental, requires explicit opt-in, and can be replaced without changes to the skill, domain, artifact store, or result schema.

## Consequences

- Rendering and workflow behavior are testable without an account or network access.
- The project does not present the observed endpoint as an official API.
- Input validation, artifact preservation, and upload remain separate capabilities.

## Evidence checked

- reMarkable Developer Portal: https://developer.remarkable.com/
- reMarkable importing/exporting support: https://support.remarkable.com/articles/Knowledge/importing-and-exporting-files
