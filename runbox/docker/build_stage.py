from __future__ import annotations

import abc
import asyncio
import contextlib
import logging
from asyncio import iscoroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any, Sequence, TypeVar, Generic, AsyncGenerator, AsyncIterator, AsyncContextManager, Callable, Awaitable
)

from aiodocker.stream import Message

from runbox import DockerExecutor, Mount, SandboxBuilder
from runbox.models import File, DockerProfile, Limits
from runbox.proto import Sandbox

T = TypeVar('T')
B = TypeVar('B')


@dataclass
class BuildState(Generic[T]):
    shared: dict[str, Any] = field(default_factory=dict)


class AbstractBuildStage(abc.ABC, Generic[T]):
    before: AbstractBuildStage[Any] | None

    def __call__(self, state: BuildState) -> AsyncContextManager[T]:
        ...

    def __rshift__(self, then: AbstractBuildStage[B]) -> AbstractBuildStage[B]:
        ...


class BaseBuildStage(AbstractBuildStage[T]):

    def __init__(self) -> None:
        self.before: AbstractBuildStage[Any] | None = None

    def __rshift__(self, then: AbstractBuildStage[B]) -> AbstractBuildStage[B]:
        then.before = self
        return then

    @contextlib.asynccontextmanager
    async def __call__(self, state: BuildState) -> AsyncIterator[T]:
        before: AsyncContextManager[T | None]
        if self.before:
            before = self.before(state)
        else:
            before = contextlib.nullcontext()

        async with before:
            stage = contextlib.asynccontextmanager(self.stage)
            async with stage(state) as data:
                logging.debug(f"Begin {self}")
                yield data
                logging.debug(f"End {self}")

    @abc.abstractmethod
    def stage(self, state: BuildState) -> AsyncGenerator[T, Any]:
        ...


class WriteFiles(BaseBuildStage[None]):

    def __init__(
        self,
        sandbox_key: str,
        directory: Path,
        files: Sequence[File],
    ):
        super().__init__()
        self.sandbox_key = sandbox_key
        self.directory = directory
        self.files = files

    async def stage(self, state: BuildState) -> AsyncGenerator[None, Any]:
        sandbox: Sandbox = state.shared[self.sandbox_key]
        await sandbox.write_files(self.directory, *self.files)
        yield

    def __repr__(self) -> str:
        return f"Write into {self.sandbox_key} {[f.name for f in self.files]}"


class MountVolume(BaseBuildStage[None]):

    def __init__(
        self,
        mount_key: str,
        target_builder_key: str,
        delete_on_dispose: bool = True,
    ):
        super().__init__()
        self.mount_key = mount_key
        self.target_builder_key = target_builder_key
        self.delete_on_dispose = delete_on_dispose

    async def stage(self, state: BuildState) -> AsyncGenerator[None, Any]:
        mount: Mount = state.shared[self.mount_key]
        current_builder: SandboxBuilder = state.shared[self.target_builder_key]
        state.shared[self.target_builder_key] = current_builder.mount(mount.volume, mount.bind)
        yield
        if self.delete_on_dispose:
            await mount.volume.delete()

    def __repr__(self) -> str:
        return f"Mount {self.mount_key} -> {self.target_builder_key}"


class CreateSandbox(BaseBuildStage[Sandbox]):

    def __init__(
        self,
        builder_key: str,
        executor_key: str,
        output_key: str | None = None
    ):
        super().__init__()
        self.builder_key = builder_key
        self.executor_key = executor_key
        self.output_key = output_key

    async def stage(self, state: BuildState) -> AsyncGenerator[Sandbox, Any]:
        builder: SandboxBuilder = state.shared[self.builder_key]
        executor: DockerExecutor = state.shared[self.executor_key]
        async with await builder.create(executor) as sandbox:
            if self.output_key:
                state.shared[self.output_key] = sandbox
            yield sandbox

    def __repr__(self) -> str:
        return f"Create sandbox {self.builder_key} -> {self.output_key}"


class Run(BaseBuildStage[Sandbox]):

    def __init__(self, sandbox_key: str, stdin: bytes | None = None):
        super().__init__()
        self.sandbox_key = sandbox_key
        self.stdin = stdin

    async def stage(self, state: BuildState) -> AsyncGenerator[Sandbox, Any]:
        sandbox: Sandbox = state.shared[self.sandbox_key]
        await sandbox.run(self.stdin)
        yield sandbox

    def __repr__(self) -> str:
        return f"Run {self.sandbox_key}"


class Wait(BaseBuildStage[Sandbox]):

    def __init__(self, sandbox_key: str):
        super(Wait, self).__init__()
        self.sandbox_key = sandbox_key

    async def stage(self, state: BuildState) -> AsyncGenerator[Sandbox, Any]:
        sandbox: Sandbox = state.shared['sandbox']
        await sandbox.wait()
        yield sandbox

    def __repr__(self):
        return f"Wait for {self.sandbox_key}"


class Get(BaseBuildStage[T]):

    def __init__(self, key: str, either: B | None = None):
        super(Get, self).__init__()
        self.key = key
        self.either = either

    async def stage(self, state: BuildState) -> AsyncGenerator[T, Any]:
        yield state.shared.get(self.key, self.either)

    def __repr__(self) -> str:
        return f"Get {self.key}"


class Set(BaseBuildStage[T]):

    def __init__(self, key: str, value: T, on_dispose: Callable[[T], Any] | None = None):
        super(Set, self).__init__()
        self.key = key
        self.value = value
        self.on_dispose = on_dispose

    async def stage(self, state: BuildState) -> AsyncGenerator[T, Any]:
        state.shared[self.key] = self.value
        yield self.value
        if self.on_dispose:
            maybe_coro = self.on_dispose(self.value)
            if iscoroutine(maybe_coro):
                await maybe_coro

    def __repr__(self):
        return f"Set {self.key} = {self.value}"


class ObserveSandbox(BaseBuildStage[None]):
    AsyncCallback = Callable[[Message, Sandbox], Awaitable[Any]]

    def __init__(self, sandbox_key: str, on_message: AsyncCallback):
        super().__init__()
        self.sandbox_key = sandbox_key
        self.on_message = on_message

    async def listener(self, sandbox: Sandbox):

        if not sandbox.stream:
            raise  # Todo...

        while message := await sandbox.stream.read_out():
            maybe_coro = self.on_message(message, sandbox)
            if iscoroutine(maybe_coro):
                await maybe_coro

    async def stage(self, state: BuildState) -> AsyncGenerator[None, Any]:
        sandbox: Sandbox = state.shared[self.sandbox_key]

        task = asyncio.create_task(
            self.listener(sandbox)
        )
        yield
        if not task.done():
            task.cancel()


class SetProfile(BaseBuildStage[SandboxBuilder]):

    def __init__(self, builder_key: str, profile: DockerProfile):
        super(SetProfile, self).__init__()
        self.builder_key = builder_key
        self.profile = profile

    async def stage(self, state: BuildState) -> AsyncGenerator[SandboxBuilder, Any]:
        builder: SandboxBuilder = state.shared[self.builder_key]
        state.shared[self.builder_key] = builder.with_profile(self.profile)
        yield builder


class SetLimits(BaseBuildStage[SandboxBuilder]):

    def __init__(self, builder_key: str, limits: Limits):
        super(SetLimits, self).__init__()
        self.limits = limits
        self.builder_key = builder_key

    async def stage(self, state: BuildState) -> AsyncGenerator[SandboxBuilder, Any]:
        builder: SandboxBuilder = state.shared[self.builder_key]
        builder = builder.with_limits(self.limits)
        state.shared[self.builder_key] = builder
        yield builder
