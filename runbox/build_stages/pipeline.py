import abc
import asyncio
import enum
import functools
from dataclasses import dataclass, field
from typing import Protocol, Mapping, Any, Sequence

from runbox import DockerExecutor
from runbox.build_stages.stages import (
    Observer, SharedState,
    BuildStage, BuildState
)

__all__ = ['Pipeline', 'BasePipeline', 'CompileAndRunPipeline']


class GroupStatus(str, enum.Enum):
    done = "done"
    failed = "failed"
    pending = "pending"


@dataclass
class Group:
    name: str
    status: GroupStatus = field(init=False, default=GroupStatus.pending)
    finalized: bool = field(init=False, default=False)


@dataclass
class GroupWithStages(Group):
    stages: list[BuildStage]


class Pipeline(Protocol):

    @property
    def meta(self) -> Mapping[str, Any]:
        return {}

    @property
    def groups(self) -> Sequence[Group]:
        return []

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

    async def finalize(self) -> None:
        ...


class BasePipeline:

    def __init__(self):
        self._groups: dict[str, GroupWithStages] = {}
        self._executor: DockerExecutor | None = None
        self._observer: Observer | None = None
        self._state: SharedState | None = {}
        self._meta: dict[str, Any] = {}

    @property
    def build_state(self) -> BuildState:
        assert self.is_valid
        return BuildState(self._executor, self._observer, self._state)  # type: ignore

    @property
    def meta(self) -> Mapping[str, Any]:
        return self._meta

    @property
    def groups(self) -> Sequence[Group]:
        return list(self._groups.values())

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
            self._groups[group].stages.extend(stages)
        else:
            self._groups[group] = GroupWithStages(group, list(stages))

        return self

    async def execute_group(self, group: str) -> None:
        assert group in self._groups, f"No group with name \"{group}\" in pipeline"
        assert self.is_valid, "Pipeline state inconsistent: executor is None or has empty groups"
        assert all(not stage.is_setup for stage in self._groups[group].stages), "Some stages have been already setup"
        group_data = self._groups[group]
        assert group_data.status == GroupStatus.pending

        for stage in group_data.stages:
            try:
                await stage.setup(self.build_state)
            except Exception as e:
                group_data.status = GroupStatus.failed
                await stage.dispose()
                raise e

    async def finalize(self) -> None:
        first_exception: Exception | None = None
        for group in self._groups.values():
            for stage in group.stages:
                if stage.is_setup and not stage.is_disposed:
                    try:
                        await stage.dispose()
                    except Exception as e:
                        first_exception = e

        if first_exception is not None:
            raise first_exception

    @property
    def is_valid(self) -> bool:
        return self._executor is not None and all(len(group.stages) > 0 for group in self._groups.values())


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


@dataclass(slots=True, frozen=True)
class AsyncTask:
    type: str


@dataclass(slots=True, frozen=True)
class ExecGroup(AsyncTask):
    type: str = field(default="exec", init=False)
    group: str


@dataclass(slots=True, frozen=True)
class Finalize(AsyncTask):
    type: str = field(default="exec", init=False)


class AsyncBasePipeline:

    def __init__(self):
        self._pipeline = BasePipeline()
        self._task_queue: asyncio.Queue[AsyncTask] = asyncio.Queue()
        self._canceled: bool = False
        self._listener_task: asyncio.Task[None] = asyncio.create_task(self._listener())

    @property
    def groups(self) -> Sequence[Group]:
        return self._pipeline.groups

    async def _listener(self) -> None:
        while not self._canceled:
            task = await self._task_queue.get()
            await self._handle(task)

    @functools.singledispatchmethod
    async def _handle(self, task: AsyncTask):
        raise ValueError("Task of this type is not supported")

    @_handle.register
    async def _exec_group_async(self, group: str) -> None:
        await self._pipeline.execute_group(group)
        await self.on_group_done(group)

    @_handle.register
    async def _finalize_async(self) -> None:
        await self._pipeline.finalize()
        await self.on_finalize()
        self._canceled = True

    @property
    def meta(self) -> Mapping[str, Any]:
        return self.meta

    def update_meta(self, meta: dict[str, Any]) -> "AsyncBasePipeline":
        self._pipeline.update_meta(meta)
        return self

    def with_executor(self, executor: DockerExecutor) -> "AsyncBasePipeline":
        self._pipeline.with_executor(executor)
        return self

    def with_observer(self, observer: Observer) -> "AsyncBasePipeline":
        self._pipeline.with_observer(observer)
        return self

    def with_initial_state(self, state: SharedState) -> "AsyncBasePipeline":
        self._pipeline.with_initial_state(state)
        return self

    def add_stages(self, group: str, *stages: BuildStage) -> "AsyncBasePipeline":
        self._pipeline.add_stages(group, *stages)
        return self

    async def execute_group(self, group: str) -> None:
        await self._task_queue.put(ExecGroup(group))

    async def finalize(self) -> None:
        await self._task_queue.put(Finalize())

    async def on_finalize(self) -> None:
        ...

    async def on_group_done(self, group: str) -> None:
        ...

    async def on_group_failed(self, group: str) -> None:
        ...
