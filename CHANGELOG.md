# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## 2026-10-24

### Added

- The factory: enrol a repo under touchlineHQ or adamsuk by adding the `factory` topic.
- Baseline in `baseline/`: squash-only settings with auto-merge and branch deletion, secret scanning
  with push protection, Dependabot alerts, the `factory-main` default-branch ruleset, standard labels,
  and files (PR template, issue form, CODEOWNERS, Dependabot config, CodeQL, changelog check,
  CHANGELOG.md stub) delivered by one `factory/sync` PR per repo.
- Per-repo `.github/factory.yml` for skipping items, required checks, approvals and code owners.
- `Factory sync` workflow: hourly and push-to-main apply, PR dry runs, and manual runs (dry run by default).
  It uses one GitHub App installation token per owner and skips cleanly without App secrets.
- Reusable changelog check (`workflow_call`), generalised from adamsuk/line.
- `app-manifest.json` and one-time GitHub App setup steps.
- Python engine with tests against mocked API responses, plus CI (ruff, pytest, actionlint).
