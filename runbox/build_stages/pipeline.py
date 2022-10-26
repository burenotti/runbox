from contextlib import suppress
from typing import Protocol, Mapping, Any

from runbox import DockerExecutor
from runbox.build_stages.stages import (
    Observer, SharedState,
    BuildStage, BuildState
)

__all__ = ['Pipeline', 'BasePipeline', 'CompileAndRunPipeline']


class Pipeline(Protocol):

    @property
    def meta(self) -> Mapping[str, Any]:
        ...

    def update_meta(self, meta: dict[str, Any]) -> "Pipeline":
        ...

    def with_executor(self, executor: DockerExecutor) -> "Pipeline":
        ...

    def with_observer(self, observer: Observer) -> "Pipeline":
        ...

    def with_initial_state(self, state: SharedState) -> "Pipeline":
        ...

    def add_stages(self, group: str, *stages: BuildStage) -> "Pipeline":
        ...

    async def execute_group(self, group: str) -> None:
        ...

    async def execute_all(self) -> None:
        ...

    async def finalize(self) -> None:
        ...


class BasePipeline:

    def __init__(self):
        self._groups: dict[str, list[BuildStage]] = {}
        self._executor: DockerExecutor | None = None
        self._observer: Observer | None = None
        self._state: SharedState | None = {}
        self._meta: dict[str, Any] = {}

    @property
    def build_state(self) -> BuildState:
        assert self.is_valid
        return BuildState(self._executor, self._observer, self._state) # type: ignore

    @property
    def meta(self) -> Mapping[str, Any]:
        return self._meta

    def update_meta(self, meta: dict[str, Any]) -> "BasePipeline":
        self._meta.update(meta)
        return self

    def with_executor(self, executor: DockerExecutor) -> "BasePipeline":
        self._executor = executor
        return self

    def with_observer(self, observer: Observer) -> "BasePipeline":
        self._observer = observer
        return self

    def with_initial_state(self, state: SharedState) -> "BasePipeline":
        self._state = state
        return self

    def add_stages(self, group: str, *stages: BuildStage) -> "BasePipeline":
        if group in self._groups:
            self._groups[group].extend(stages)
        else:
            self._groups[group] = list(stages)

        return self

    async def execute_group(self, group: str) -> None:
        assert group in self._groups, f"No group with name \"{group}\" in pipeline"
        assert self.is_valid, "Pipeline state inconsistent: executor is None or has empty groups"
        assert all(not stage.is_setup for stage in self._groups[group]), "Some stages have been already setup"

        for stage in self._groups[group]:
            try:
                await stage.setup(self.build_state)
            except Exception as e:
                await stage.dispose()
                raise e

    async def finalize(self) -> None:
        for group in self._groups.values():
            for stage in group:
                if stage.is_setup and not stage.is_disposed:
                    with suppress(Exception):
                        await stage.dispose()

    @property
    def is_valid(self) -> bool:
        return self._executor is not None and all(len(stage) > 0 for stage in self._groups.values())


class CompileAndRunPipeline(BasePipeline):

    def __init__(
        self,
        build_group: str = "build",
        run_group: str = "run",
    ):
        super().__init__()
        self._build_group = build_group
        self._run_group = run_group

    async def build(self) -> None:
        await self.execute_group(self._build_group)

    async def run(self) -> None:
        await self.execute_group(self._run_group)
