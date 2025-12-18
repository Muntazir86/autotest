import pytest

from autotest.config import AutotestConfig
from autotest.core.errors import HookError


def test_error():
    with pytest.raises(HookError):
        AutotestConfig.from_str("hooks = 'test.config.hooks.error'")


def test_empty(capsys):
    AutotestConfig.from_str("hooks = 'test.config.hooks.hello'")
    captured = capsys.readouterr()
    assert "HELLO" in captured.out
