---
name: latest-docs
description: Fetch a library, framework, or API's current official documentation and changelog, then report what changed from what training data or existing code assumes — renamed or removed APIs, new required parameters, deprecations. Use when the user names a specific library or framework and asks to check the latest docs, verify the current API, or confirm code isn't calling a deprecated or renamed method.
---

# Check Latest Docs

## Quick start

Name the library, and its version if known. Add the code or API calls
to verify if you want them checked. This skill fetches the library's
current docs and reports the delta.

Examples: "Check the latest docs for Zod v4, did the API change?" or
"Verify `src/db.ts` still matches Prisma's current client API."

## Workflow

1. **Identify the library and version.** Take it from the request. If
   no version is given and a manifest or lockfile is available, read
   the pinned version from there.
2. **Locate the current official source.** Prefer, in order: the
   library's own docs site, its GitHub README/CHANGELOG/release notes,
   its published API reference. Avoid third-party tutorials — they lag
   the real docs and can already be stale themselves.
3. **Fetch the relevant pages.** Pull the API reference for the symbols
   in question and the changelog or release notes since the version in
   use (or since a recent baseline if no version is known).
4. **Report the delta.** List what differs from the commonly assumed or
   older API: renamed or removed functions, new required parameters,
   deprecation notices, breaking changes, migration notes.
5. **If a target file is given**, point out each call site that uses an
   outdated API as `file:line`, with the corrected current call.
6. **Cite sources** with the URL and, if visible, the doc's version or
   date. A docs page with no version marker is weaker evidence than one
   that names a release.

## Rules

- Never report a deprecation or rename from memory. Confirm it against
  a page fetched during this run.
- If the docs can't be reached — a private package, no public docs —
  say so plainly instead of falling back to training-data assumptions.
