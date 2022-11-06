from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PosixPath
from typing import (
    Any,
    TypeVar,
    Protocol,
    AsyncContextManager,
    AsyncIterable,
)

from pydantic import BaseModel, root_validator

from runbox import DockerExecutor, SandboxBuilder, DockerSandbox
from runbox.models import File, Limits, DockerProfile
from .exceptions import NonZeroExitCodeError, MemoryLimitError, CpuLimitError

__all__ = [
    "Observer",
    "UseSandbox",
    "UseVolume",
    "WriteFiles",
    "SharedState",
    "BuildState",
    "BuildStage",
    "StreamType",
    "default_stages",
    "LoadableFile",
]


def default_stages() -> dict[str, str]:
    return {
        "use_sandbox": "runbox.build_stages:UseSandbox",
        "use_volume": "runbox.build_stages:UseVolume",
    }


class BuildStageError(Exception):

    def __init__(self, message: str):
        super(BuildStageError, self).__init__(message)


T = TypeVar("T")
B = TypeVar("B")


class StreamType(int, Enum):
    stdout = 1
    stderr = 2


class Observer(Protocol):

    @property
    def stdin(self) -> AsyncIterable[str]:
        ...

    async def write_output(self, key: str, data: str, stream: StreamType):
        ...


SharedState = dict[str, Any]


@dataclass
class BuildState:
    executor: DockerExecutor
    observer: Observer | None = None
    shared: SharedState = field(default_factory=dict)


class BuildStage(Protocol):
    class Params(BaseModel):
        pass

    def __init__(self, params: Params):
        ...

    @property
    def is_setup(self) -> bool:
        pass

    @property
    def is_disposed(self) -> bool:
        pass

    async def setup(self, state: BuildState) -> None:
        pass

    async def dispose(self) -> None:
        pass


class WriteFiles:
    class Params(BaseModel):
        key: str
        file_keys: list[str]
        volume: str
        profile: DockerProfile = DockerProfile(
            image="alpine:latest",
            workdir=Path("/tmp"),
        )

    def __init__(self, params: Params):
        self._is_setup = False
        self._is_disposed = False
        self.params = params

    @property
    def is_setup(self) -> bool:
        return self._is_setup

    @property
    def is_disposed(self) -> bool:
        return self._is_disposed

    @staticmethod
    def get_files(keys: list[str], shared: SharedState) -> list[File]:
        collected_files: list[File] = []
        for key in keys:
            if files := shared.get(key):
                if isinstance(files, list) and all(isinstance(f, File) for f in files):
                    collected_files.extend(files)
                elif isinstance(files, File):
                    collected_files.append(files)
                else:
                    raise TypeError("Value is not a file or list of files")
            else:
                raise KeyError(f"Key '{key}' is not in shared state")
        return collected_files

    async def setup(self, state: BuildState) -> None:
        self._is_setup = True
        files = self.get_files(self.params.file_keys, state.shared)
        volume = state.shared[self.params.volume]
        builder = SandboxBuilder() \
            .with_profile(self.params.profile) \
            .mount(volume, self.params.profile.workdir or '/', readonly=False) \
            .add_files(*files)

        async with await builder.create(state.executor):
            pass

    async def dispose(self) -> None:
        self._is_disposed = True


class UseVolume:
    class Params(BaseModel):
        key: str

    def __init__(self, params: Params):
        self._is_setup = False
        self._is_disposed = False
        self.params = params
        self._volume_ctx: AsyncContextManager | None = None
        self._state: BuildState | None = None

    @property
    def is_setup(self) -> bool:
        return self._is_setup

    @property
    def is_disposed(self) -> bool:
        return self._is_disposed

    async def setup(self, state: BuildState) -> None:
        self._is_setup = True
        self._state = state
        self._volume_ctx = state.executor.workdir()
        self._state.shared[self.params.key] = await self._volume_ctx.__aenter__()

    async def dispose(self) -> None:
        self._is_disposed = True
        if self._volume_ctx:
            await self._volume_ctx.__aexit__(None, None, None)

        if self._state:
            del self._state.shared[self.params.key]


class SandboxMount(BaseModel):
    key: str
    bind: PosixPath
    readonly: bool = False


class LoadableFile(File):
    path: Path | None = None

    @root_validator(pre=True)
    def load_content(cls, v: dict[str, Any]):
        if (v.get('path') is not None) == (v.get('content') is not None):
            raise ValueError("Either 'path' or 'content' must be specified, not both")

        if v.get('path') is not None:
            v['path'] = Path(v['path'])
            mode = 'r' if v.get('content_type', 'text') == 'text' else 'rb'
            with v['path'].open(mode) as file:
                v['content'] = file.read()
        return v


class UseSandbox:
    class Params(BaseModel):
        key: str
        profile: DockerProfile
        limits: Limits = Limits()
        files: list[LoadableFile] = []
        mounts: list[SandboxMount] = []
        attach: bool = True

    def __init__(self, params: Params):
        self.params = params
        self._is_setup = False
        self._is_disposed = False
        self._sandbox: DockerSandbox | None = None
        self._state: BuildState | None = None
        self._output_listener_task: asyncio.Task | None = None
        self._input_listener_task: asyncio.Task | None = None

    @property
    def is_setup(self) -> bool:
        return self._is_setup

    @property
    def is_disposed(self) -> bool:
        return self._is_disposed

    async def input_listener(self, sandbox: DockerSandbox):
        if not sandbox.stream:
            raise  # Todo...

        if not self._state:
            raise BuildStageError("Listener was called before setup")

        if self._state.observer is None:
            raise BuildStageError("Can't attach if no observer was given")

        async for message in self._state.observer.stdin:
            if message is not None:
                await sandbox.stream.write_in(message.encode("utf-8"))

    async def output_listener(self, sandbox: DockerSandbox):

        if not sandbox.stream:
            raise  # Todo...

        if not self._state:
            raise BuildStageError("Listener was called before setup")

        if self._state.observer is None:
            raise BuildStageError("Can't attach if no observer was given")

        while message := await sandbox.stream.read_out():
            data = message.data.decode("utf-8")
            await self._state.observer.write_output(
                self.params.key, data, message.stream
            )

    async def setup(self, state: BuildState) -> None:
        self._is_setup = True
        self._state = state

        builder = (
            SandboxBuilder()
            .with_limits(self.params.limits)
            .with_profile(self.params.profile)
            .add_files(*self.params.files)
        )

        builder = functools.reduce(
            lambda b, m: b.mount(state.shared[m.key], m.bind, m.readonly),
            self.params.mounts,
            builder,
        )

        self._sandbox = await builder.create(state.executor)
        await self._sandbox.run()
        if self.params.attach:
            if state.observer is None:
                raise BuildStageError("Can't attach if no observer was given")

            self._output_listener_task = asyncio.create_task(
                self.output_listener(self._sandbox)
            )
            self._input_listener_task = asyncio.create_task(
                self.input_listener(self._sandbox)
            )

        await self._sandbox.wait()

        result = await self._sandbox.state()

        if result.memory_limit:
            raise MemoryLimitError[UseSandbox.Params](self.params.limits, self.params.key, self.params, self)

        if result.cpu_limit:
            raise CpuLimitError[UseSandbox.Params](self.params.limits, self.params.key, self.params, self)

        if result.exit_code != 0:
            raise NonZeroExitCodeError[UseSandbox.Params](result.exit_code, self.params.key, self.params, self)

        self._state = state
        state.shared[self.params.key] = self._sandbox

    async def dispose(self) -> None:
        self._is_disposed = True
        if self._state and self.params.key in self._state.shared:
            del self._state.shared[self.params.key]
        if self._sandbox:
            await self._sandbox.delete()

        if self._input_listener_task and not self._input_listener_task.done():
            self._input_listener_task.cancel()
        if self._output_listener_task and not self._output_listener_task.done():
            await self._output_listener_task
