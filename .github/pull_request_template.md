<!-- Title must be a Conventional Commit, e.g. `feat(router): add shared subscriptions`.
     It becomes the squash-merge commit and decides the next version:
     feat -> minor, fix/docs/chore/... -> patch, `type!:` -> breaking. -->

Closes #<!-- issue number -->

## What

<!-- What changes and why. -->

## How to test

<!-- Commands or steps a reviewer can run. -->

## Checklist

- [ ] Branch was created from the issue (`<issue-number>-<short-slug>`)
- [ ] Tests added or updated; `pytest` passes locally
- [ ] `ruff check .`, `ruff format --check .` and `mypy` pass
- [ ] Public API changes are documented in `README.md`
