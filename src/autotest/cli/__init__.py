from __future__ import annotations

from autotest.cli.commands import Group, run, autotest
from autotest.cli.commands.run.context import ExecutionContext
from autotest.cli.commands.run.events import LoadingFinished, LoadingStarted
from autotest.cli.commands.run.executor import handler
from autotest.cli.commands.run.handlers import EventHandler
from autotest.cli.ext.groups import GROUPS, OptionGroup

__all__ = [
    "autotest",
    "run",
    "EventHandler",
    "ExecutionContext",
    "LoadingStarted",
    "LoadingFinished",
    "add_group",
    "handler",
]


def add_group(name: str, *, index: int | None = None) -> Group:
    """Add a custom options group to `st run`."""
    if index is not None:
        GROUPS[name] = OptionGroup(name=name, order=index)
    else:
        GROUPS[name] = OptionGroup(name=name)
    return Group(name)
