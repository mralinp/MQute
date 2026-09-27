import importlib.util
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "release.py"
_spec = importlib.util.spec_from_file_location("release", _PATH)
assert _spec is not None
assert _spec.loader is not None
release = importlib.util.module_from_spec(_spec)
sys.modules["release"] = release
_spec.loader.exec_module(release)


@pytest.mark.parametrize(
    "title",
    ["feat: add x", "fix(router): handle y", "feat(api)!: drop z", "chore(deps): bump paho", "docs: readme (#12)"],
)
def test_conventional_titles(title):
    assert release.is_conventional(title)


@pytest.mark.parametrize("title", ["Add x", "feat:missing space", "feature: x", "fix: ", "Merge pull request #1"])
def test_non_conventional_titles(title):
    assert not release.is_conventional(title)


@pytest.mark.parametrize(
    ("current", "messages", "expected"),
    [
        (None, ["feat: first"], "0.1.0"),
        ("1.2.3", ["fix: a"], "1.2.4"),
        ("1.2.3", ["docs: a", "Merge branch 'x'"], "1.2.4"),
        ("1.2.3", [], "1.2.4"),
        ("1.2.3", ["fix: a", "feat: b"], "1.3.0"),
        ("1.2.3", ["feat!: b"], "2.0.0"),
        ("1.2.3", ["refactor: b\n\nBREAKING CHANGE: removed x"], "2.0.0"),
        ("0.4.1", ["feat(core)!: b"], "0.5.0"),
    ],
)
def test_next_version(current, messages, expected):
    assert release.next_version(current, messages) == expected


def test_cli_check_title(capsys):
    assert release.main(["check-title", "feat: ok"]) == 0
    assert release.main(["check-title", "nope"]) == 1
    assert "Conventional Commit" in capsys.readouterr().out
    assert release.main([]) == 2


def test_cli_next_version_uses_git(monkeypatch, capsys):
    monkeypatch.setattr(release, "latest_tag", lambda: "v1.0.0")
    monkeypatch.setattr(release, "commit_messages", lambda since: ["feat: new"])
    assert release.main(["next-version"]) == 0
    assert capsys.readouterr().out.strip() == "1.1.0"
