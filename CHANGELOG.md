# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## 2026-10-24 (gh extension)

Reworked into a GitHub CLI extension. The reasons: no private keys to create or
guard, nothing to host, and something anyone can reuse if it is open-sourced.

### Changed

- Renamed the repo from `adamsuk/factory` to `adamsuk/gh-factory`. Install it with
  `gh extension install adamsuk/gh-factory` and run it as `gh factory`.
- Commands: `plan` (read-only dry run), `apply` (asks unless `--yes`), `enrol` (adds the topic,
  then applies) and `leave` (removes the topic only).
- Auth comes only from the caller's `gh` login: every request goes through `gh api`.
  No tokens or secrets are stored.
- Config is portable. Built-in defaults use the authenticated user as owner and code owner.
  A user config at `~/.config/gh-factory/config.yml`, `--config` and `--owner` can override them.
  Owners for touchlineHQ and adamsuk now live in `examples/config.yml`.
- A custom baseline (`--baseline` or `baseline:`) falls back to the built-in one for anything missing.
- Items that need admin rights to read are shown as `unknown` instead of guessed.
- The reusable changelog workflow is now `adamsuk/gh-factory/.github/workflows/changelog.yml@main`.
- Vendored pure-Python PyYAML, so the extension needs only python3 (3.10+).

### Added

- MIT licence and an open-source-ready README covering install, commands, config, overrides,
  custom baselines, gh scopes, the rights each operation needs, and limitations on GitHub Free.
- Optional `drift-check.yml`: a weekly or manual read-only plan with the default `GITHUB_TOKEN`
  against public repos. It only reports.
- Tests for the CLI commands and config resolution. CI runs on Python 3.10 and 3.13 and checks
  that the extension runs with a bare python3.

### Removed

- The GitHub App: `app-manifest.json`, the `FACTORY_APP_ID` / `FACTORY_APP_PRIVATE_KEY` token logic,
  and the hourly `sync.yml` workflow.
- The hardcoded touchlineHQ/adamsuk defaults (`factory.yml`).

## 2026-10-24

### Added

- The factory: enrol a repo by adding the `factory` topic.
- Baseline in `baseline/`: squash-only settings with auto-merge and branch deletion, secret scanning
  with push protection, Dependabot alerts, the `factory-main` default-branch ruleset, standard labels,
  and files (PR template, issue form, CODEOWNERS, Dependabot config, CodeQL, changelog check,
  CHANGELOG.md stub) delivered by one `factory/sync` PR per repo.
- Per-repo `.github/factory.yml` for skipping items, required checks, approvals and code owners.
- Reusable changelog check (`workflow_call`), generalised from adamsuk/line. It skips PRs opened by
  Dependabot (`skip_authors` input).
- Dependabot for this repo, keeping deliberate lower bounds in `pyproject.toml` (`increase-if-necessary`).
- Python engine with tests against mocked API responses, plus CI (ruff, pytest, actionlint).
