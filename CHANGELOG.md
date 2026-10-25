# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Every PR adds a dated entry (`## YYYY-MM-DD (topic)`) under `## [Unreleased]`. Releases are
automatic: after a `feat`, `fix`, `perf` or breaking change merges, the release workflow opens a
`chore(release): vX.Y.Z` PR that moves those entries under `## [X.Y.Z] - YYYY-MM-DD`, and merging
that PR tags and publishes the release.

## [Unreleased]

## [0.5.0] - 2026-10-25

### 2026-10-25 (multi-line test command)

#### Fixed

- A multi-line `agents.test_command` now shows in the plan as a fenced code block under the Agents
  line, so its line breaks are kept instead of rendering as one space-joined command.

### 2026-10-25 (agents review bot and test command)

#### Added

- `agents.review_bot` (`coderabbit` or `none`, default `none`) and `agents.test_command` (an
  optional string) in `.github/factory.yml`. Both are validated, shown on the plan's Agents line
  and included in `--json`. The plan also notes `merge: true` without the `reviewer` role, since
  every agent merge needs PR Reviewer's review (from the adamsuk/gh-factory#16 trial).

## [0.4.0] - 2026-10-25

#### 2026-10-25 (CodeRabbit config)

##### Added

- `.coderabbit.yaml` as a baseline file (skip key `coderabbit`). It sets the `chill` profile,
  en-GB, no draft reviews, and a review instruction to treat the PR description as a claim and to
  flag changes to tests, CI, lockfiles and agent instructions. `inheritance: true` keeps org or app
  settings for everything else, and a hand-made file without the marker is left alone
  (adamsuk/software-factory#26).

## [0.3.0] - 2026-10-25

### 2026-10-25 (code-owner review)

#### Added

- Two per-repo overrides in `.github/factory.yml`. `codeowner_paths` lists the paths CODEOWNERS
  owns instead of `*` (`/.github/` is always owned), and `require_code_owner_review` turns on
  code-owner review in the `factory-main` ruleset. Together they make changes to agent
  instructions, tests, CI or lockfiles wait for a person while other PRs don't
  (adamsuk/software-factory#6, #25). Both are validated, and `plan` notes code-owner review in the
  ruleset summary. `plan` warns when `require_code_owner_review` is on without
  `codeowner_paths`, since every PR would then wait for a code owner. Nothing changes for repos
  that don't set them.

## [0.2.0] - 2026-10-25

### 2026-10-25 (automatic releases)

#### Added

- Automatic semver releases. `.github/workflows/release.yml` is a reusable workflow that reads the
  Conventional Commit titles since the last tag (`feat` is minor; `fix` and `perf` are patch; `!` or
  `BREAKING CHANGE:` is major; `chore`, `docs`, `ci`, `test` and the rest release nothing) and opens
  or refreshes a `chore(release): vX.Y.Z` PR. That PR moves the `## [Unreleased]` entries in
  `CHANGELOG.md` under the new version heading and bumps the version in `version_files`. Merging it
  tags the merge commit and publishes a GitHub release with that version's changelog section as
  notes. It uses only the default `GITHUB_TOKEN`. gh-factory runs it from `auto-release.yml` on
  every push to main.
- `.github/workflows/pr-title.yml`: a reusable check that fails a PR whose title is not a
  Conventional Commit, since the squash-merge commit takes the PR title. gh-factory requires its
  `PR title` check.
- Tests for the release logic, including an end-to-end run against a local git remote.

#### Changed

- `CHANGELOG.md` groups released entries under version headings: everything up to the first
  release is now under `## [0.1.0] - 2026-10-25`, with its headings one level down.
- README: pin a release with `--pin vX.Y.Z` from the Releases page, and a "Releases" section.

### 2026-10-25 (agents may merge here)

#### Changed

- `.github/factory.yml` turns on `agents: { merge: true }`, so the factory agents may merge their own
  gh-factory PRs once every required check listed in that file is green. Roles stay the default
  (builder, reviewer) and the issue label stays `factory`.

### 2026-10-25 (issue template placeholder)

#### Fixed

- The baseline issue form's "Acceptance criteria" box uses a `placeholder` instead of a prefilled
  `value`. A prefilled `- [ ] ` counted as an answer, so `required: true` never stopped an empty
  checklist. This matches touchlineHQ/.github#2, so the next apply no longer reverts that fix.
  gh-factory's own copy is updated too.

### 2026-10-25 (agents section)

#### Added

- An optional `agents:` section in a repo's `.github/factory.yml`, for the factory's coding and
  review agents: `merge` (default `false`), `roles` (any of `intake`, `research`, `builder`,
  `reviewer`; default `builder` and `reviewer`) and `issue_label` (default `factory`). It is
  validated like the rest of the file, and an invalid section stops the factory touching the repo.
- `gh factory plan` shows each repo's agent settings in the Markdown plan and as an `agents` object
  in `--json`, with notes when `merge: true` has no required checks to gate it, or when the issue
  label is not a baseline label. gh-factory never acts on these settings; the agents read them.
- README: an "Agents" section with examples.

#### Changed

- The baseline `factory` label's description now reads "Opened by gh-factory, or an issue queued
  for the factory agents", because agents pick up issues with that label. The next apply updates
  the label's description in enrolled repos.

## [0.1.0] - 2026-10-25

### 2026-10-25 (v0.1.0)

#### Changed

- Auto-merge is only enabled when a repo's effective config has at least one required check.
  With no checks and no approvals, a PR set to auto-merge would merge instantly. Such repos keep
  auto-merge off, or have it turned off, and the plan says why.
- Every action in delivered workflows is pinned to a full commit SHA with a `# vX.Y.Z` comment,
  from the new `baseline/actions.yml`: checkout v7.0.1, codeql-action v4.39.1. The reusable changelog
  workflow is pinned via `workflows_ref` (default `283fa17… # main`, new `workflows_ref_comment`).
  These match touchlineHQ/.github#2. gh-factory's own workflows are pinned too, including actionlint
  1.7.12, and a test keeps them in step with the baseline.
- The PR template's changelog line now reads "CHANGELOG.md updated, if this repo keeps one (or the
  `skip-changelog` label applied)". Conditional wording was chosen over conditional rendering because
  touchlineHQ/.github's template is the org-wide default for repos with and without a changelog,
  and a single file can't know which repo it is shown in.
- gh-factory's `.github/factory.yml` now lists its real CI checks as `required_checks`, so its own
  `factory-main` ruleset gates merges and auto-merge is on.

#### Added

- README: pin a release with `gh extension install adamsuk/gh-factory --pin v0.1.0`; a section on pinned actions.
- The `gh-extension` topic, and release v0.1.0.

### 2026-10-25

#### Changed

- gh-factory is enrolled in itself, and its own drift is cleared, so `gh factory plan adamsuk/gh-factory`
  shows no changes and no drift.
  - `.github/pull_request_template.md`, `.github/dependabot.yml` and `.github/workflows/codeql.yml`
    are now exactly what the baseline delivers, with the `factory-managed` marker.
  - `.github/factory.yml` skips `changelog-check`. Here `.github/workflows/changelog.yml` is the
    reusable `workflow_call` source that enrolled repos call, so it can't be replaced by a caller of itself.
- The generated Dependabot config uses `versioning-strategy: increase-if-necessary` for pip. That adopts
  this repo's hand-written choice: deliberate lower bounds are kept, and exact pins still get bumped.
- Factory sync PRs keep carrying the `skip-changelog` label (unchanged). A baseline sync is housekeeping,
  not a product change, and writing into a repo's CHANGELOG.md would break the marker rule
  (CHANGELOG.md is create-only).

### 2026-10-24 (gh extension)

Reworked into a GitHub CLI extension. The reasons: no private keys to create or
guard, nothing to host, and something anyone can reuse if it is open-sourced.

#### Changed

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
- When the token is not a user (e.g. `GITHUB_TOKEN` in Actions), CODEOWNERS defaults to the first owner.
- The reusable changelog workflow is now `adamsuk/gh-factory/.github/workflows/changelog.yml@main`.
- Vendored pure-Python PyYAML, so the extension needs only python3 (3.10+).

#### Added

- MIT licence and an open-source-ready README covering install, commands, config, overrides,
  custom baselines, gh scopes, the rights each operation needs, and limitations on GitHub Free.
- Optional `drift-check.yml`: a weekly or manual read-only plan with the default `GITHUB_TOKEN`
  against public repos. It only reports.
- Tests for the CLI commands and config resolution. CI runs on Python 3.10 and 3.13 and checks
  that the extension runs with a bare python3.

#### Removed

- The GitHub App: `app-manifest.json`, the `FACTORY_APP_ID` / `FACTORY_APP_PRIVATE_KEY` token logic,
  and the hourly `sync.yml` workflow.
- The hardcoded touchlineHQ/adamsuk defaults (`factory.yml`).

### 2026-10-24

#### Added

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
