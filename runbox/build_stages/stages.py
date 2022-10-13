from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any, Sequence, TypeVar, Protocol,
    AsyncContextManager, AsyncIterable, Type
)

from pydantic import BaseModel

from runbox import DockerExecutor, Mount, SandboxBuilder, DockerSandbox
from runbox.models import File, Limits, DockerProfile
from runbox.proto import Sandbox

__all__ = [
    'Observer', 'UseSandbox', 'UseVolume',
    'SharedState', 'BuildState', 'BuildStage',
    'StreamType',
]


class BuildStageError(Exception):

    def __init__(self, message: str):
        super(BuildStageError, self).__init__(message)


T = TypeVar('T')
B = TypeVar('B')


class StreamType(int, Enum):
    stdout = 1
    stderr = 2


class Observer(Protocol):
    stdin: AsyncIterable[str]

    async def write_output(self, key: str, data: str, stream: StreamType):
        ...


SharedState = dict[str, Any]


@dataclass
class BuildState:
    executor: DockerExecutor
    observer: Observer | None = None
    shared: SharedState = field(default_factory=dict)


class BuildStage(Protocol):
    Params: Type[BaseModel]

    def __init__(self, params: BaseModel):
        ...

    async def setup(self, state: BuildState) -> None:
        pass

    async def dispose(self) -> None:
        pass


class WriteFiles:

    def __init__(
        self,
        sandbox_key: str,
        directory: Path,
        files: Sequence[File],
    ):
        self.sandbox_key = sandbox_key
        self.directory = directory
        self.files = files

    async def setup(self, state: BuildState) -> None:
        sandbox: Sandbox = state.shared[self.sandbox_key]
        await sandbox.write_files(self.directory, *self.files)

    async def dispose(self) -> None:
        pass

    def __repr__(self) -> str:
        return f"Write into {self.sandbox_key} {[f.name for f in self.files]}"


class UseVolume:
    class Params(BaseModel):
        key: str

    def __init__(self, params: Params):
        self.params = params
        self._volume_ctx: AsyncContextManager | None = None
        self._state: BuildState | None = None

    async def setup(self, state: BuildState):
        self._state = state
        self._volume_ctx = state.executor.workdir()
        self._state.shared[self.params.key] = await self._volume_ctx.__aenter__()

    async def dispose(self):

        if self._volume_ctx:
            await self._volume_ctx.__aexit__(None, None, None)

        if self._state:
            del self._state.shared[self.params.key]


class UseSandbox:
    class Params(BaseModel):
        key: str
        profile: DockerProfile
        limits: Limits = Limits()
        files: list[File] = []
        mounts: list[Mount] = []
        attach: bool = True

    def __init__(self, params: Params):
        self.params = params
        self._sandbox: DockerSandbox | None = None
        self._state: BuildState | None = None
        self._output_listener_task: asyncio.Task | None = None
        self._input_listener_task: asyncio.Task | None = None

    async def input_listener(self, sandbox: DockerSandbox):
        if not sandbox.stream:
            raise  # Todo...

        if not self._state:
            raise BuildStageError("Listener was called before setup")

        if self._state.observer is None:
            raise BuildStageError("Can't attach if no observer was given")

        async for message in self._state.observer.stdin:
            if message is not None:
                await sandbox.stream.write_in(message.encode('utf-8'))

    async def output_listener(self, sandbox: DockerSandbox):

        if not sandbox.stream:
            raise  # Todo...

        if not self._state:
            raise BuildStageError("Listener was called before setup")

        if self._state.observer is None:
            raise BuildStageError("Can't attach if no observer was given")

        while message := await sandbox.stream.read_out():
            data = message.data.decode('utf-8')
            await self._state.observer.write_output(self.params.key, data, message.stream)

    async def setup(self, state: BuildState) -> None:
        self._state = state

        builder = SandboxBuilder() \
            .with_limits(self.params.limits) \
            .with_profile(self.params.profile) \
            .add_files(*self.params.files)

        builder = functools.reduce(
            lambda b, m: b.mount(m.volume, m.bind, m.readonly),
            self.params.mounts, builder
        )

        self._sandbox = await builder.create(state.executor)
        await self._sandbox.run()
        if self.params.attach:
            if state.observer is None:
                raise BuildStageError("Can't attach if no observer was given")

            self._output_listener_task = asyncio.create_task(self.output_listener(self._sandbox))
            self._input_listener_task = asyncio.create_task(self.input_listener(self._sandbox))

        await self._sandbox.wait()

        self._state = state
        state.shared[self.params.key] = self._sandbox

    async def dispose(self) -> None:
        if self._state:
            del self._state.shared[self.params.key]
        if self._sandbox:
            await self._sandbox.delete()

        if self._input_listener_task and not self._input_listener_task.done():
            self._input_listener_task.cancel()
        if self._output_listener_task and not self._output_listener_task.done():
            await self._output_listener_task
