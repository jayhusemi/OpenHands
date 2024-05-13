from dataclasses import dataclass
from typing import ClassVar

from opendevin.core.schema import ActionType

from .base import ExecutableAction


@dataclass
class FileReadAction(ExecutableAction):
    """
    Reads a file from a given path.
    Can be set to read specific lines using start and end
    Default lines 0:-1 (whole file)
    """
    path: str
    start: int = 0
    end: int = -1
    thoughts: str = ''
    action: str = ActionType.READ
    runnable: ClassVar[bool] = True

    @property
    def message(self) -> str:
        return f'Reading file: {self.path}'


@dataclass
class FileWriteAction(ExecutableAction):
    path: str
    content: str
    start: int = 0
    end: int = -1
    thoughts: str = ''
    action: str = ActionType.WRITE
    runnable: ClassVar[bool] = True

    @property
    def message(self) -> str:
        return f'Writing file: {self.path}'
