# reMarkable Summary Export

A Codex plugin project for turning task, research, and meeting summaries into paper-friendly documents and sending them to reMarkable.

## Status

The plugin manifest and first skill contract are scaffolded. No live upload is performed yet.

## Proposed MVP

1. Format the current Codex summary as Markdown.
2. Preview the title, destination folder, and output type.
3. Call a local export adapter.
4. Support native notebook export through RCU first.
5. Add PDF upload as a fallback.

The backend is deliberately separated from the skill so a future official reMarkable API can replace the initial adapter without changing the user-facing workflow.

## Project structure

```text
.codex-plugin/plugin.json
skills/export-summary-to-remarkable/
  SKILL.md
  agents/openai.yaml
  references/backends.md
scripts/
```

## Next implementation step

Create the `remarkable-summary-export` CLI, define a local configuration schema, and add a dry-run mode that produces the final Markdown without uploading it.
