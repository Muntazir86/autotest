import pytest

import autotest


@pytest.fixture(autouse=True)
def unregister_global():
    yield
    Autotest.auths.unregister()
