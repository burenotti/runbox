from __future__ import annotations

from runbox import DockerExecutor, SandboxBuilder
from .proto import TestCase, TestResult


class BaseTestSuite:

    def __init__(
        self,
        builder: SandboxBuilder,
    ) -> None:
        self.builder = builder
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
