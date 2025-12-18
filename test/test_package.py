import sys
from importlib import metadata


def test_dev_version(monkeypatch, mocker):
    # When Autotest is run in dev environment without installation
    monkeypatch.delitem(sys.modules, "autotest.core.version")
    mocker.patch("importlib.metadata.version", side_effect=metadata.PackageNotFoundError)
    from autotest.core.version import AUTOTEST_VERSION

    # Then it's version is "dev"
    assert AUTOTEST_VERSION == "dev"
