# gh-factory

A [GitHub CLI](https://cli.github.com) extension that applies one standard setup
to every repo you tag. Add a topic to a repo, run `gh factory apply`, and the
repo gets the same settings, branch ruleset, labels and starter files as every
other enrolled repo. Change the standard once and re-apply to bring every repo
in line.

- **No App, no private keys, no server.** It runs as you, with your existing
  `gh` login. It stores no tokens or secrets.
- **Safe by default.** `plan` is a read-only dry run: the client refuses any
  write. File changes always arrive as one pull request per repo. It never
  pushes to a default branch and never overwrites a file you own.
- **Bring your own standard.** The built-in baseline is a starting point. Point
  `--baseline` at your own directory.

## Install

Requirements: [`gh`](https://cli.github.com) logged in (`gh auth login`), and
`python3` 3.10 or newer. Nothing else: the one dependency (PyYAML) is vendored.

```sh
gh extension install adamsuk/gh-factory --pin v0.1.0   # a fixed release (recommended)
gh extension install adamsuk/gh-factory                # or track main
gh factory --help
```

Unpinned installs upgrade with `gh extension upgrade factory`. To move a pinned install
to a newer release, reinstall it with the new `--pin` tag. Releases are listed
[here](https://github.com/adamsuk/gh-factory/releases).

## Quickstart

```sh
gh factory plan OWNER/REPO       # see what would change, read-only
gh factory enrol OWNER/REPO      # add the `factory` topic, show the plan, confirm, apply
gh factory plan                  # dry run across every enrolled repo
gh factory apply                 # re-apply everywhere (asks first)
```

## Commands

| Command | What it does |
| --- | --- |
| `gh factory plan [OWNER/REPO ...]` | Dry run. With no arguments, covers every non-archived repo carrying the topic under the configured owners. Named repos are planned even if they're not enrolled, and marked as such. Never writes. |
| `gh factory apply [OWNER/REPO ...] [--yes]` | Plans, shows the plan, asks for confirmation, then applies. Named repos must be enrolled. Without a terminal it refuses unless `--yes` is given. |
| `gh factory enrol OWNER/REPO [--yes]` | Shows the plan, asks, adds the topic, then applies. `enroll` works too. |
| `gh factory leave OWNER/REPO` | Removes the topic only. Settings, the ruleset, labels and files stay in place, and an open factory PR is left for you to close. |

Common flags: `--owner NAME` (repeatable), `--config FILE`, `--baseline DIR`,
`--json FILE` (machine-readable plan), `--summary FILE` (append the Markdown
plan, e.g. `$GITHUB_STEP_SUMMARY`).

Exit codes: `0` ok, `1` an error in at least one repo, `2` usage error or
confirmation declined.

## What the built-in baseline applies

| Item | Key (for opt-outs) | How |
| --- | --- | --- |
| Squash merge only, PR title/body as the commit, branches deleted after merge. Auto-merge is allowed only when the repo has at least one required check; with none, a PR set to auto-merge would merge instantly, so it is kept (or turned) off | `settings` | API, in place |
| Secret scanning and push protection, where GitHub offers it | `secret-scanning` | API, in place |
| Dependabot vulnerability alerts | `vulnerability-alerts` | API, in place |
| Ruleset `factory-main` on the default branch: PR required (0 approvals by default), required checks from config (none by default), no force-push, no deletion | `ruleset` | API; updated in place, other rulesets never touched |
| Labels `skip-changelog`, `cutting edge`, `dependencies`, `github_actions`, `factory`, `bug`, `enhancement`, `documentation` | `labels` | API; created or updated, others never deleted |
| `.github/pull_request_template.md` with a "CHANGELOG.md updated, if this repo keeps one" checkbox (reads correctly as an org-wide default template too) | `pr-template` | one PR |
| `.github/ISSUE_TEMPLATE/task.yml` issue form with acceptance criteria | `issue-template` | one PR |
| `.github/CODEOWNERS` (`*` and `/.github/` owned by `@you` by default) | `codeowners` | one PR |
| `.github/dependabot.yml` for the ecosystems found in the repo | `dependabot` | one PR |
| `.github/workflows/codeql.yml` for the languages found | `codeql` | one PR |
| `.github/workflows/changelog.yml`, calling the [reusable changelog check](#reusable-changelog-check) | `changelog-check` | one PR |
| `CHANGELOG.md` stub, only if the repo has none | `changelog-stub` | one PR |

`files` skips every file item at once.

**Pull request, never main.** File changes are one commit on the
`factory/sync` branch, on top of the default branch, with one PR per repo,
labelled `factory` and `skip-changelog`. Re-running refreshes the same branch
and PR, and does nothing if they're already up to date.

**The marker rule.** Delivered files start with a `factory-managed` line. The
factory only overwrites files that carry it. A file that exists without the
marker is reported as **drift** and left alone. Delete the marker line to take
ownership of a file. `CHANGELOG.md` is only ever created.

Plan statuses: **create / update / enable / open-pr / update-pr** (changes),
**drift** (left alone), **unavailable** (GitHub doesn't offer it here),
**unknown** (needs admin rights to read), **skipped**, **error**.

## Configuration

Settings are resolved in this order, later ones winning:

1. **Built-in defaults.** The owner is you (the authenticated `gh` user), the
   topic is `factory`, CODEOWNERS is `@you`, approvals are 0, and there are no
   required checks.
2. **A config file.** `--config FILE`, else `$GH_FACTORY_CONFIG`, else
   `~/.config/gh-factory/config.yml` (or `$XDG_CONFIG_HOME/gh-factory/config.yml`)
   if it exists.
3. **Flags.** `--owner` and `--baseline`.

```yaml
# ~/.config/gh-factory/config.yml (every key optional)
owners: [my-org, my-user]       # accounts searched for enrolled repos
topic: factory                  # enrolment topic
codeowners: ["@my-user"]        # CODEOWNERS entries
approvals: 0                    # required approving reviews (0-10)
required_checks: []             # status checks required on every repo
baseline: ./my-baseline         # custom baseline; relative to this file
sync_branch: factory/sync
marker: factory-managed
workflows_repo: adamsuk/gh-factory   # where delivered workflows find the reusable check
workflows_ref: <commit sha>         # pinned commit of the reusable workflows
workflows_ref_comment: main         # written after the pin as `# main`
```

See [`examples/config.yml`](examples/config.yml).

## Per-repo overrides

A repo can opt out of items, or set its own checks and approvals, with
`.github/factory.yml` on its default branch:

```yaml
# .github/factory.yml (every key optional)
skip:                 # item keys from the table above, or `files` for all files
  - codeql
  - labels
approvals: 1          # required approving reviews (0-10)
required_checks:      # exact check names that already run on this repo's PRs
  - Test and lint
  - Analyze (javascript-typescript)
codeowners:
  - "@my-org/maintainers"
```

The factory never makes up check names. Listing a check that never runs blocks
every PR. An invalid override file stops the factory from touching that repo,
and the error shows in the plan.

## Custom baselines

`--baseline DIR` (or `baseline:` in config) points at a directory shaped like
[`baseline/`](baseline):

```
my-baseline/
  settings.yml        # repository settings and security toggles
  ruleset.yml         # the default-branch ruleset
  labels.yml          # standard labels
  actions.yml         # commit SHAs that delivered workflows pin actions to
  files/              # templates, at the path they are delivered to
    .github/pull_request_template.md
    .github/ISSUE_TEMPLATE/task.yml
    .github/workflows/changelog.yml
    CHANGELOG.md
```

`actions.yml` lists the commit SHA (and version, written as a `# vX.Y.Z` comment)
that every delivered workflow pins each action to.

Anything missing falls back to the built-in baseline, so you can override just
`labels.yml` or a single template. Templates may use `{{marker}}`,
`{{workflows_repo}}`, `{{workflows_ref}}`, `{{workflows_pin}}` (ref plus comment) and `{{repo}}`. CODEOWNERS,
Dependabot and CodeQL are generated from what's in each repo.

## Permissions and gh scopes

`gh factory` uses your `gh` login and can do only what you can. For a classic
OAuth token (the `gh auth login` default):

- `repo`: everything on repos, including private ones.
- `workflow`: needed to deliver files under `.github/workflows/` (CodeQL and
  the changelog check). Add it with `gh auth refresh -s workflow`.
- `read:org`: lets discovery list an org's private repos. `gh` requests it by
  default.
- `admin:org` is **not** needed. The factory uses repo rulesets, never org
  settings.

Rights needed on each repo:

| Operation | Needs |
| --- | --- |
| `plan` of files, labels, ruleset, PRs | read |
| `plan` of settings, secret scanning, vulnerability alerts | admin (otherwise shown as **unknown**) |
| Labels, the `factory/sync` branch and the PR | write |
| Settings, secret scanning, vulnerability alerts, the ruleset, adding or removing the topic (`enrol`, `leave`) | **admin** |

## Limitations on GitHub Free

On private repos under GitHub Free (personal accounts and Free orgs), GitHub
offers no rulesets or branch protection, no secret scanning or push protection,
and no CodeQL code scanning. The plan marks these **unavailable** and carries on.
Public repos get everything. Org-wide rulesets need a paid plan, which is why
the factory applies everything repo by repo.

## Optional drift check in Actions

[`.github/workflows/drift-check.yml`](.github/workflows/drift-check.yml) runs
`gh factory plan` weekly, or on demand, using only the default `GITHUB_TOKEN`.
It needs no secrets and makes no writes. That token can only see **public**
repos, and it can't read admin-only items, which show as **unknown**. It
reports in the job summary and never fails on drift. Set the `FACTORY_OWNERS`
repository variable (space-separated) to choose the owners.

## Pinned actions

Every `uses:` in delivered workflows is pinned to a full commit SHA with a
`# vX.Y.Z` comment, taken from [`baseline/actions.yml`](baseline/actions.yml).
The reusable changelog workflow is pinned the same way, through `workflows_ref`.
Every delivered `dependabot.yml` covers `github-actions`, so Dependabot proposes
bumps. Delivered workflows are factory-managed, though, so to make a bump stick
everywhere, update `baseline/actions.yml` and re-apply. A test fails if
gh-factory's own workflows and `baseline/actions.yml` disagree, so a Dependabot
bump here can't silently diverge from the baseline.

## Reusable changelog check

[`.github/workflows/changelog.yml`](.github/workflows/changelog.yml) fails a PR
that doesn't touch `CHANGELOG.md`, unless the PR has the `skip-changelog`
label or was opened by Dependabot. Use it from any repo:

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened, labeled, unlabeled]
permissions:
  contents: read
  pull-requests: read
jobs:
  changelog:
    uses: adamsuk/gh-factory/.github/workflows/changelog.yml@<commit-sha> # v0.1.0
    # with: { changelog_file: CHANGELOG.md, skip_label: skip-changelog, skip_authors: "dependabot[bot]" }
```

## Develop

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
ruff check . && ruff format --check . && pytest
gh extension install .          # run your checkout as `gh factory`
```

Every change needs a dated entry in [CHANGELOG.md](CHANGELOG.md).

## Licence

[MIT](LICENSE). Vendored PyYAML is MIT too ([licence](src/factory/_vendor/yaml/LICENSE)).
