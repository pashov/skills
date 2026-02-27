# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Versioning Guide

Given a version number `MAJOR.MINOR.PATCH`:

- **MAJOR** - breaking changes to skill interfaces or manifest schema
- **MINOR** - new skills or backwards-compatible additions
- **PATCH** - bug fixes, prompt improvements, documentation updates

Pre-release versions are tagged as `v1.0.0-beta.1`, `v1.0.0-rc.1`, etc.

---

## [Unreleased]

### Added
- `audit` skill — fast security feedback on Solidity changes during development
- `audit-helper` skill — full audit prep for security researchers (build, architecture, threat model)
- `lint` skill — Solidity linter covering NatSpec, naming, visibility, custom errors, and more
- Plugin manifest (`.claude-plugin/plugin.json`) and `marketplace.json` for Claude plugin distribution
- Repository scaffolding: `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`
- GitHub issue and PR templates

---

<!-- Add new releases above this line using the format below:

## [1.1.0] - YYYY-MM-DD

### Added
- New `skills/my-skill` skill

### Changed
- Improved prompt in `skills/audit`

### Fixed
- Corrected model compatibility list in `skills/lint/SKILL.md`

### Removed
- Deprecated `skills/old-skill`

-->

[Unreleased]: https://github.com/pashov/skills/compare/HEAD...HEAD
