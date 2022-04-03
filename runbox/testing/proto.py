from __future__ import annotations

from enum import Enum
from typing import Protocol

from pydantic import BaseModel

from runbox import DockerExecutor
from runbox.proto import Sandbox


class TestStatus(Enum):
    ok = 'OK'
    compile_error = 'CE'
    time_limit = 'TL'
    memory_limit = 'ML'
    runtime_error = 'RE'
    server_error = 'SE'
    wrong_answer = 'WA'

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.__str__()


class TestResult(BaseModel):
    status: TestStatus
    why: str | None

    # None if timelimit occurred
    duration: float | None


class TestCase(Protocol):

    async def exec(self, sandbox: Sandbox) -> TestResult:
        ...


class TestSuite(Protocol):

    def add_tests(self, *tests: TestCase) -> TestSuite:
        ...

    def remove_test(self, test: TestCase) -> bool:
        ...

    # This is dependency inversion principle violation and must be refactored
    # But now RunBox doesn't know any other executor, so it could be ok now.
    # I don't pass here a sandbox instead of executor, because execution
    # of a suite may need many containers.
    async def exec(self, executor: DockerExecutor) -> list[TestResult]:
        ...
