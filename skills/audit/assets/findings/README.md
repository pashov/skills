# Findings

This directory holds two kinds of reports:

- **Reports from previous `/audit` runs** — written automatically as `{project-name}-pashov-ai-audit-report-{timestamp}.md` each time the skill runs.
- **External audit reports** — drop any third-party or manual audit `.md` files here.

On each run the skill reads every file in this directory and re-verifies whether previously reported issues still exist in the current code. Issues still present are carried forward with a "Previously reported — still present" note. Issues that are no longer present are silently skipped.
