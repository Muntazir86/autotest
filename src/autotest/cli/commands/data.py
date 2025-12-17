from dataclasses import dataclass

from autotest.config import AutotestConfig


@dataclass
class Data:
    config: AutotestConfig

    __slots__ = ("config",)
