from contextlib import suppress
from typing import Protocol

from runbox import DockerExecutor
from runbox.build_stages.stages import (
    Observer, SharedState,
    BuildStage, BuildState
)

__all__ = ['ExecutionPipeline', 'DefaultExecutionPipeline']


class ExecutionPipeline(Protocol):
    stages: list[BuildStage]

    def add_stages(self, *stages: BuildStage) -> "ExecutionPipeline":
        ...

    async def execute(
        self,
        executor: DockerExecutor,
        observer: Observer | None = None,
        initial_shared_state: SharedState = None,
    ) -> None:
        ...


class DefaultExecutionPipeline:

    def __init__(
        self,
        stages: list[BuildStage] | None = None
    ):
        self.stages = stages[:] if stages else []

    def add_stages(self, *stages: BuildStage) -> ExecutionPipeline:
        self.stages.extend(stages)
        return self

    async def execute(
        self,
        executor: DockerExecutor,
        observer: Observer | None = None,
        initial_shared_state: SharedState = None,
    ) -> None:
        build_state = BuildState(
            executor=executor,
            observer=observer,
            shared=initial_shared_state or {}
        )

        try:
            for stage in self.stages:
                await stage.setup(build_state)
        finally:
            for stage in self.stages:
                with suppress(Exception):
                    await stage.dispose()
