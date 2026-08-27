# Public release checklist

Use this checklist immediately before changing the repository to public. Repository settings are not version-controlled, so each item requires an explicit GitHub UI or API action.

## Repository presentation

- Set the About description to: `Codex plugin that renders Markdown as paper-friendly PDFs and publishes them idempotently to a reMarkable library.`
- Add topics: `remarkable`, `codex`, `openai-codex`, `markdown`, `markdown-to-pdf`, `mcp`, `python`, `docker`, and `productivity`.
- Upload a solid-background social preview at 1280 by 640 pixels and keep the title readable at small sizes.
- Confirm the CI badge resolves after the first public Actions run.
- Keep the repository title, README H1, opening description, and plugin metadata concise and consistent. Avoid keyword stuffing.

GitHub documents that topics help people find related projects, a README should explain what the project does and how to start, and a custom social preview improves shared repository links. Google recommends concise descriptive titles, visible explanatory text, useful link text, and descriptive image alt text.

Sources checked 2026-08-27:

- [GitHub: Classifying a repository with topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics)
- [GitHub: About repository READMEs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)
- [GitHub: Customizing a social media preview](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview)
- [Google Search Central: SEO starter guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide)

## Community and security

- Enable Issues for bugs and compatibility reports.
- Enable Discussions only if there is capacity to moderate support questions.
- Enable private vulnerability reporting, secret scanning, and push protection where available.
- Verify that GitHub's community profile detects `README.md`, `LICENSE`, `CONTRIBUTING.md`, and `SECURITY.md`.
- Require the `CI` workflow on the default branch and block direct pushes that bypass it.
- Keep Actions permissions read-only unless a future job documents why it needs more.

GitHub's community profile and security guidance recommend contribution instructions, a security policy, least-privilege workflow permissions, and full-SHA action pinning.

Sources checked 2026-08-27:

- [GitHub: Community profiles for public repositories](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories)
- [GitHub: Adding a security policy](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/add-security-policy)
- [GitHub Actions: Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)

## Privacy audit

- Review current tracked files and all reachable history for credentials, personal paths, private documents, and response captures.
- Review commit author names and email addresses. Configure a GitHub-provided no-reply address for future commits if a personal address should not be public.
- Treat history rewriting as a separate destructive migration: coordinate it, rotate any exposed secret first, preserve a backup, and warn collaborators before a force push.
- Confirm no generated PDF, credential, token, SQLite database, or state volume is tracked.

## Release evidence

- Run every command in the README development section from a clean checkout.
- Validate the plugin manifest with the current Codex plugin validator.
- Install the plugin from the documented source layout and start a new Codex task to verify tool discovery.
- Keep a real-account upload optional and explicitly authorized. If performed, use synthetic Markdown and report web-library and physical-device observations separately.
