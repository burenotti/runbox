from __future__ import annotations

from runbox import DockerExecutor
from .proto import TestCase, TestResult
from ..proto import SandboxFactory


class BaseTestSuite:

    def __init__(
        self,
        sandbox_factory: SandboxFactory,
    ) -> None:
        self.builder = sandbox_factory
        self.tests: list[TestCase] = []

    def add_tests(self, *tests: TestCase) -> BaseTestSuite:
        self.tests.extend(tests)
        return self

    def remove_test(self, test: TestCase) -> bool:
        try:
            self.tests.remove(test)
            return True
        except ValueError:
            return False

    async def exec(self, executor: DockerExecutor) -> list[TestResult]:
        result = []
        sandbox = await self.builder.create(executor)
        async with sandbox:
            for test_case in self.tests:
                result.append(await test_case.exec(sandbox))

        return result
