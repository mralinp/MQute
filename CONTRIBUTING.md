# Contributing to MQute

Thanks for helping. This document is the single source of truth for how work
flows through the project.

## Workflow: issue → branch → pull request → release

1. **Open an issue** for every change (feature, bug, refactor, docs) using a
   template. Discuss the approach there before writing much code.
2. **Assign the issue** to the person doing the work. One assignee per issue;
   unassigned issues are free to pick up, just comment first.
3. **Create a branch from the issue**, named `<issue-number>-<short-slug>`,
   for example `42-shared-subscriptions`. GitHub's *Create a branch* button on
   the issue page does this for you. One issue, one branch.
4. **Open a pull request** into `main` early (draft is fine). The PR:
   - has a [Conventional Commit](https://www.conventionalcommits.org) title,
     e.g. `feat(router): add shared subscriptions` (checked by CI);
   - links the issue with `Closes #42` in the description;
   - passes CI: lint, types, tests on Python 3.10–3.14, and a build check.
5. **Review and squash-merge.** The PR title becomes the commit on `main`.
6. **Release happens automatically.** Every merge to `main` runs CI again,
   computes the next version, tags it, creates a GitHub release and publishes
   to PyPI. Nobody bumps versions by hand.

### How the PR title picks the version

| Title | Example | Bump |
| --- | --- | --- |
| `feat: ...` | `feat(testing): add async test client` | minor `1.2.3 → 1.3.0` |
| `fix: ...`, `docs:`, `refactor:`, `perf:`, `test:`, `build:`, `ci:`, `chore:`, `style:`, `revert:` | `fix(transport): resubscribe after reconnect` | patch `1.2.3 → 1.2.4` |
| `type!: ...` or a `BREAKING CHANGE:` footer | `feat(app)!: rename serve() to run_async()` | major `1.2.3 → 2.0.0` (minor while below 1.0) |

## Local setup

```bash
git clone https://github.com/mralinp/mqute.git
cd mqute
python -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip          # pip >= 25.1 for --group
python -m pip install -e . --group dev
```

## Checks (run before pushing; CI runs the same)

```bash
ruff check .            # lint
ruff format .           # format
mypy                    # strict type checking of src/
pytest --cov            # tests with coverage (must stay >= 90%)
```

Integration tests talk to a real broker and are skipped unless
`MQUTE_TEST_BROKER_URL` is set:

```bash
docker run -d -p 1883:1883 eclipse-mosquitto:2 mosquitto -c /mosquitto-no-auth.conf
MQUTE_TEST_BROKER_URL=mqtt://localhost:1883 pytest
```

## Code standards

- Small, single-purpose modules and functions; names that explain themselves.
- Public API is typed and documented with a short docstring; `mypy --strict` passes.
- No new runtime dependencies without discussion in an issue. The core depends
  on `paho-mqtt` only; optional integrations go in extras.
- Every behaviour change comes with tests. Prefer `mqute.testing.TestClient`
  for app-level behaviour and plain unit tests for pure functions.
- Keep the README in sync with the public API.

## Maintainer setup (one-off)

- PyPI: add a *trusted publisher* for project `mqute`, workflow `release.yml`,
  environment `pypi`.
- GitHub: create the `pypi` environment; protect `main` (require PRs and the
  CI checks); allow **squash merging** only and use the PR title as the commit
  message.
