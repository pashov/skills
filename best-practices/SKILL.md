---
name: best-practices
description: Research current best practices and idiomatic patterns for a language, framework, or library from official docs and style guides, then either answer a best-practices question directly or review given code against those patterns. Use when the user asks "what's idiomatic here", "is this best practice", "review this for best practices", or wants code checked against current stack conventions.
---

# Best Practices & Idiomatic Review

## Quick start

State the stack — language, framework, or library. Point at files or a
diff if you want a review. Without a target, this skill answers the
question directly.

Examples: "What's the idiomatic way to handle errors in Go?" or "Review
`src/api/users.ts` against current Express best practices."

## Workflow

1. **Identify the stack.** Take it from the request. If unstated and a
   target file exists, infer it from the file extension or the
   project's manifest (`package.json`, `Cargo.toml`, `go.mod`, and so
   on). Confirm with the user if it stays ambiguous.
2. **Research from primary sources.** Search and fetch the maintainer's
   own docs and style guide first — the language's own guide (Effective
   Go, PEP 8, the Rust API Guidelines), a framework's official docs, or
   a library's own README and CHANGELOG. Treat blog posts and forum
   answers as secondary. Use them only to confirm a primary source,
   never as the sole basis for a claim.
3. **Answer or review.**
   - No target: answer the question directly and cite the sources
     checked.
   - Target given: read the files. Compare each relevant pattern
     against what you found. List concrete deviations as `file:line` —
     what the code does, what the idiom is, and the fix. Skip anything
     already idiomatic. Do not rewrite the whole file.
4. **Cite sources.** Trace every claim to a source fetched during this
   run. Never state a "best practice" from memory alone. List the URLs
   checked at the end.

## Rules

- Ground every claim in a source read this session. Do not rely on
  training-data memory of a style guide.
- Prefer the official convention over a trendy one when the docs
  disagree with common practice.
- Flag when a "best practice" is contested or version-dependent instead
  of stating one answer as universal.
