import hypothesis.errors
import pytest
from hypothesis import HealthCheck, Phase, given, settings
from hypothesis_openapi import openapis

import autotest
import autotest.engine
from autotest.config import HealthCheck as AutotestHealthCheck
from autotest.config import AutotestConfig
from autotest.core.errors import InvalidSchema
from autotest.engine import events

IGNORED_EXCEPTIONS = (hypothesis.errors.Unsatisfiable, InvalidSchema, hypothesis.errors.FailedHealthCheck)
config = AutotestConfig.from_dict({})
config.projects.default.update(suppress_health_check=[AutotestHealthCheck.all])
config.projects.default.phases.update(phases=["examples", "fuzzing"])
config.projects.default.generation.update(max_examples=10)


@given(schema=openapis(version="2.0") | openapis(version="3.0"))
@settings(max_examples=20, phases=[Phase.generate], deadline=None, suppress_health_check=list(HealthCheck))
@pytest.mark.usefixtures("mocked_call")
def test_random_schemas(schema):
    schema = autotest.openapi.from_dict(schema, config=config)
    for event in Autotest.engine.from_schema(schema).execute():
        assert not isinstance(event, events.FatalError), repr(event)
        if isinstance(event, events.NonFatalError) and not isinstance(event.value, IGNORED_EXCEPTIONS):
            raise AssertionError(str(event.info)) from event.value
