from __future__ import annotations

from runbox import DockerExecutor
from .proto import TestCase, TestResult
from ..models import DockerProfile, File, Limits


class BaseTestSuite:

    def __init__(
        self,
        profile: DockerProfile,
        limits: Limits,
        files: list[File],
    ) -> None:
        self.files = files
        self.limits = limits
        self.profile = profile
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
        async with executor.workdir() as workdir:
            result = []
            container = await executor.create_container(
                self.profile, self.files, workdir, self.limits)

            async with container as sandbox:
                for test_case in self.tests:
                    result.append(await test_case.exec(sandbox))

        return result
