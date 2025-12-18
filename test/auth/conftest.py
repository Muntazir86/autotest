import pytest

import autotest
Autotest = autotest  # Alias for backward compatibility


@pytest.fixture(autouse=True)
def unregister_global():
    yield
    autotest.auths.unregister()
