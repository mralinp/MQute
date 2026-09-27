"""Release helper used by CI. Standard library only.

    python scripts/release.py check-title "feat(router): add shared subscriptions"
    python scripts/release.py next-version

Versions follow SemVer and are derived from Conventional Commits since the
latest ``vX.Y.Z`` tag:

* ``type!:`` or a ``BREAKING CHANGE:`` footer -> major (minor while < 1.0)
* ``feat:``                                    -> minor
* anything else                                -> patch
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from enum import IntEnum

TYPES = ("feat", "fix", "perf", "refactor", "docs", "test", "build", "ci", "chore", "style", "revert")
TITLE = re.compile(rf"^(?P<type>{'|'.join(TYPES)})(\([\w./ -]+\))?(?P<breaking>!)?: \S.*$")
INITIAL_VERSION = "0.1.0"


class Bump(IntEnum):
    PATCH = 0
    MINOR = 1
    MAJOR = 2


def is_conventional(title: str) -> bool:
    return TITLE.match(title.strip()) is not None


def bump_for(message: str) -> Bump:
    subject, _, body = message.strip().partition("\n")
    match = TITLE.match(subject.strip())
    if (match and match["breaking"]) or re.search(r"^BREAKING[ -]CHANGE:", body, re.MULTILINE):
        return Bump.MAJOR
    if match and match["type"] == "feat":
        return Bump.MINOR
    return Bump.PATCH


def next_version(current: str | None, messages: Iterable[str]) -> str:
    if current is None:
        return INITIAL_VERSION
    major, minor, patch = (int(part) for part in current.split("."))
    bump = max((bump_for(message) for message in messages), default=Bump.PATCH)
    if bump is Bump.MAJOR and major == 0:
        bump = Bump.MINOR  # SemVer 0.x: breaking changes bump the minor version
    if bump is Bump.MAJOR:
        return f"{major + 1}.0.0"
    if bump is Bump.MINOR:
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def latest_tag() -> str | None:
    try:
        return _git("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*.[0-9]*.[0-9]*").strip() or None
    except subprocess.CalledProcessError:
        return None


def commit_messages(since: str | None) -> list[str]:
    revision = f"{since}..HEAD" if since else "HEAD"
    return [message for message in _git("log", "--format=%B%x00", revision).split("\x00") if message.strip()]


def main(argv: Sequence[str]) -> int:
    if len(argv) == 2 and argv[0] == "check-title":
        if is_conventional(argv[1]):
            return 0
        print(f"PR title {argv[1]!r} is not a Conventional Commit, e.g. 'feat(router): add shared subscriptions'.")
        print(f"Allowed types: {', '.join(TYPES)}. Add '!' after the type for breaking changes.")
        return 1
    if argv == ["next-version"]:
        tag = latest_tag()
        print(next_version(tag.removeprefix("v") if tag else None, commit_messages(tag)))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
