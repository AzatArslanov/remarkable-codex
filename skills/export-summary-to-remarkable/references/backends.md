# Export backends

## Recommended MVP: local adapter

Implement a small command-line adapter with this contract:

```text
remarkable-summary-export send \
  --input summary.md \
  --title "Project summary" \
  --folder "Codex/Summaries" \
  --format notebook
```

Return JSON on standard output:

```json
{"ok":true,"documentId":"...","title":"Project summary","format":"notebook"}
```

Read credentials from the operating-system credential store or an ignored configuration file. Never accept secrets as ordinary command-line arguments.

## Native notebook transport

Use a local tool capable of converting Markdown to native reMarkable typed text. RCU currently offers this capability and avoids depending on an undocumented cloud conversion endpoint. Keep RCU behind an adapter so it can be replaced later.

## PDF transport

Convert Markdown to PDF with Pandoc, then upload through a configured local or cloud client. PDF is annotatable but its underlying text is not editable as notebook text.

## Private cloud transport

The reMarkable web and desktop clients use private cloud endpoints. Community clients can upload PDF and EPUB, but the API has no supported stability or compatibility guarantee. Require an explicit opt-in setting for this backend and isolate it behind the same adapter contract.

## Browser conversion

Pandoc can convert Markdown to DOCX and reMarkable Connect can convert Word documents to notebooks in the web app. Until a public API exists, this path requires interactive use or browser automation and should not be the default unattended backend.
