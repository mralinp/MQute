import sys
import types

import pytest

from mqute import MQute, cli
from mqute.testing import MemoryTransport


@pytest.fixture
def fake_module(monkeypatch):
    module = types.ModuleType("fake_mqute_app")
    module.app = MQute(transport=MemoryTransport())
    module.not_an_app = object()
    monkeypatch.setitem(sys.modules, "fake_mqute_app", module)
    return module


def test_load_app(fake_module):
    assert cli.load_app("fake_mqute_app:app") is fake_module.app


@pytest.mark.parametrize("target", ["fake_mqute_app", "fake_mqute_app:not_an_app", "fake_mqute_app:missing"])
def test_load_app_rejects_bad_targets(fake_module, target):
    with pytest.raises(ValueError, match=r"module:attribute|not an MQute"):
        cli.load_app(target)


def test_run_command(fake_module, monkeypatch):
    ran = []
    monkeypatch.setattr(fake_module.app, "run", lambda: ran.append(True))
    monkeypatch.delenv("MQUTE_BROKER_URL", raising=False)
    assert cli.main(["run", "fake_mqute_app:app", "--broker", "mqtt://example", "--log-level", "debug"]) == 0
    assert ran == [True]


def test_run_command_reports_import_errors(capsys):
    with pytest.raises(SystemExit):
        cli.main(["run", "does_not_exist_anywhere:app"])
    assert "No module named" in capsys.readouterr().err
