# factory

A software factory for every repo under **touchlineHQ** and **adamsuk**. Add the
`factory` topic to a repo and, within the hour, it gets the same standard setup
as every other enrolled repo. Change the standard here and every enrolled repo
follows.

It runs in GitHub Actions in this repo, with a GitHub App token, so it needs
nothing running anywhere else.

## What an enrolled repo gets

| Item | Key (for opt-outs) | How it is applied |
| --- | --- | --- |
| Squash merge only, PR title/body as the commit, auto-merge allowed, branches deleted after merge | `settings` | API, in place |
| Secret scanning and push protection (where GitHub offers it: free on public repos) | `secret-scanning` | API, in place |
| Dependabot vulnerability alerts | `vulnerability-alerts` | API, in place |
| Ruleset `factory-main` on the default branch: PR required (0 approvals by default), required checks from the repo's override list (none by default), no force-push, no deletion | `ruleset` | API; updated in place, other rulesets never touched |
| Labels `skip-changelog`, `cutting edge`, `dependencies`, `github_actions`, `factory`, `bug`, `enhancement`, `documentation` | `labels` | API; created or updated, others never deleted |
| `.github/pull_request_template.md` with a "CHANGELOG.md updated" checkbox | `pr-template` | one PR |
| `.github/ISSUE_TEMPLATE/task.yml` issue form with acceptance criteria | `issue-template` | one PR |
| `.github/CODEOWNERS` (`* @adamsuk` and `/.github/`) | `codeowners` | one PR |
| `.github/dependabot.yml` for the ecosystems found in the repo | `dependabot` | one PR |
| `.github/workflows/codeql.yml` for the languages found (needs a public repo or GitHub Code Security) | `codeql` | one PR |
| `.github/workflows/changelog.yml`, calling the reusable check in this repo | `changelog-check` | one PR |
| `CHANGELOG.md` stub, only if the repo has none | `changelog-stub` | one PR |

`files` skips every file item at once.

The standard lives in [`baseline/`](baseline): `settings.yml`, `ruleset.yml`,
`labels.yml` and the templates in `baseline/files/`. Global defaults (owners,
topic, approvals, code owners) live in [`factory.yml`](factory.yml).

### Files are always delivered by pull request

The factory never pushes to a default branch. File changes go on the
`factory/sync` branch as one commit on top of the default branch, with one PR
per repo (labelled `factory` and `skip-changelog`). Later runs refresh the same
branch and PR, and do nothing if it is already up to date.

A file the factory delivers carries a `factory-managed` marker on its first
line. The factory only overwrites a file that has the marker. If a file exists
without it, the factory leaves it alone and reports it as **drift**. Delete the
marker line to take ownership of a file. `CHANGELOG.md` is only ever created,
never changed.

### Not available on every plan

touchlineHQ is on GitHub Free and adamsuk is a personal account. On private
repos there, GitHub does not offer rulesets, secret scanning or CodeQL. The
plan reports those items as **unavailable** rather than failing.

## Enrol a repo

Add the topic `factory` to the repo (repo page → ⚙ next to About → Topics), or:

```sh
gh repo edit OWNER/REPO --add-topic factory
```

The next hourly run applies the baseline. To see the plan first, run the
**Factory sync** workflow by hand with `dry_run` ticked and `repo` set to
`OWNER/REPO`.

To leave, remove the topic. Nothing is undone: settings, the ruleset and labels
stay as they are, and you can change them freely.

## Opt out of items, or set checks and approvals

Add `.github/factory.yml` to the repo's default branch:

```yaml
# .github/factory.yml (all keys optional)
skip:                 # items from the table above, or `files` for all files
  - codeql
  - labels
approvals: 1          # required approving reviews (0-10). Default 0.
required_checks:      # exact check names from the repo's own CI. Default: none.
  - Test and lint
  - Analyze (javascript-typescript)
codeowners:           # replaces the default @adamsuk
  - "@adamsuk"
  - "@touchlineHQ/maintainers"
```

The factory never makes up check names: list only checks that already run on
the repo's PRs, or every PR will be blocked. An invalid file stops the factory
from touching that repo, and the error shows in the run summary.

## How it runs

[`.github/workflows/sync.yml`](.github/workflows/sync.yml):

| Trigger | Mode |
| --- | --- |
| Hourly schedule | apply |
| Push to `main` touching `baseline/`, `src/`, `factory.yml` or the workflow | apply |
| Pull request touching the same | dry run, plan in the job summary |
| Manual (**Run workflow**) | dry run by default; untick `dry_run` to apply; optional `repo` |

It runs one job per owner in `factory.yml`, each with its own App installation
token. Discovery uses the installation's repository list, so the factory only
sees repos the App is installed on. Each run writes the plan (what changed, or
would change, per repo) to the job summary and uploads it as `plan.json`.

If the App secrets are missing, the workflow skips with a notice and stays green.

## One-time GitHub App setup

The factory acts as its own App, not as adamsuk, so its changes are clearly
attributed and its access is limited to the repos you install it on.

**Permissions** (repository): Administration read and write, Contents read and
write, Pull requests read and write, Issues read and write (labels), Workflows
read and write, Metadata read. No account or organisation permissions, no
webhook, no events. They're listed in [`app-manifest.json`](app-manifest.json).

1. **Create the App.** Open this link while signed in as adamsuk. It pre-fills
   the name, permissions and a disabled webhook:

   <https://github.com/settings/apps/new?name=adamsuk-factory&url=https%3A%2F%2Fgithub.com%2Fadamsuk%2Ffactory&public=true&webhook_active=false&administration=write&contents=write&pull_requests=write&issues=write&workflows=write&metadata=read>

   Check the permissions match the list above. Under "Where can this GitHub App
   be installed?" keep **Any account**. That's needed to install an App owned
   by adamsuk on the touchlineHQ org. Other people could install it, but
   nothing runs for them, because only owners in `factory.yml` are processed
   and only you hold the private key. Click **Create GitHub App**.
2. **Note the App ID** at the top of the App's settings page.
3. **Generate a private key** (App settings → Private keys → Generate). A
   `.pem` file downloads.
4. **Install it on both owners.** App settings → Install App:
   - **touchlineHQ**: choose **All repositories**, or **Only select
     repositories**. Enrolment still needs the `factory` topic either way.
   - **adamsuk**: the same.
5. **Add two secrets to this repo.** adamsuk/factory → Settings → Secrets and
   variables → Actions → New repository secret:
   - `FACTORY_APP_ID`: the App ID (or Client ID) from step 2
   - `FACTORY_APP_PRIVATE_KEY`: the full contents of the `.pem` file

   Or from a terminal:

   ```sh
   gh secret set FACTORY_APP_ID --repo adamsuk/factory --body "<app id>"
   gh secret set FACTORY_APP_PRIVATE_KEY --repo adamsuk/factory < adamsuk-factory.*.private-key.pem
   ```

   Then delete the downloaded `.pem`.
6. **Check it.** Actions → Factory sync → Run workflow (dry run). Both owner
   jobs should go green and report the number of repos scanned, and 0 enrolled
   until you add the topic somewhere.

## Develop

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
ruff check . && ruff format --check . && pytest
python -m factory                     # dry run with your gh login (read-only)
python -m factory --repo OWNER/REPO   # one enrolled repo
```

Without `GITHUB_TOKEN` or `GH_TOKEN` the engine calls the API through your
logged-in `gh` CLI. A dry run is enforced read-only: the client refuses any
non-GET request. Every change needs a dated entry in [CHANGELOG.md](CHANGELOG.md).
The reusable changelog check is
[`.github/workflows/changelog.yml`](.github/workflows/changelog.yml).
