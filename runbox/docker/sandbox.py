import asyncio
from pydantic import BaseModel, Field
from aiodocker.containers import DockerContainer
from aiodocker.stream import Message, Stream
from datetime import datetime, timedelta
from typing import Any, Protocol
from runbox.docker.exceptions import SandboxError


class SandboxState(BaseModel):
    status: str = Field(..., alias="Status")
    exit_code: int | None = Field(None, alias="ExitCode")
    started_at: datetime = Field(..., alias="StartedAt")
    finished_at: datetime | None = Field(None, alias="FinishedAt")
    memory_limit: bool = Field(..., alias="OOMKilled")
    cpu_limit: bool = Field(..., alias="CpuLimit")

    @property
    def duration(self) -> timedelta:
        if self.finished_at:
            return self.finished_at - self.started_at
        else:
            return timedelta(seconds=-1)


class Sandbox(Protocol):

    async def run(self, stdin: bytes | None = None):
        ...

    async def wait(self, timeout: float = None):
        ...

    async def state(self) -> SandboxState:
        ...


class SandboxInput(Protocol):

    async def write_in(self, send: bytes) -> None:
        ...


class SandboxOutput(Protocol):

    async def read_out(self) -> Message | None:
        ...


class SandboxIO(SandboxInput, SandboxOutput, Protocol):
    ...


class DockerSandbox:

    def __init__(
        self,
        name: str,
        container: DockerContainer,
        timeout: float,
    ) -> None:
        self.name = name
        self._container = container
        self._timeout = timeout
        self._cpu_limit: bool = False
        self._timeout_task: asyncio.Task | None = None
        self._stream: Stream | None = None

    async def wait(self):
        try:
            if self._timeout_task is None:
                raise SandboxError("Sandbox is not running")

            await self._timeout_task

        except asyncio.exceptions.TimeoutError:
            self._cpu_limit = True
            await self._container.kill()

    async def set_timeout(self):
        loop = asyncio.get_running_loop()
        waiter = self._container.wait(timeout=self._timeout)
        self._timeout_task = loop.create_task(waiter)

    def __await__(self):
        return self.wait().__await__()

    async def run(self) -> SandboxIO:
        await self._container.start()

        stream = self._container.attach(
            stdin=True, stdout=True, stderr=True
        )
        self._stream = stream

        await self.set_timeout()

        return stream

    async def state(self) -> SandboxState:
        container_info = await self._container.docker.containers.get(self._container.id)
        state = container_info._container['State']

        state = {**state, 'CpuLimit': self._cpu_limit}
        return create_sandbox_state(state)

    async def log(self, stdout: bool = False, stderr: bool = False) -> list[str]:
        return await self._container.log(stdout=stdout, stderr=stderr)


def create_sandbox_state(state: dict[str, Any]) -> SandboxState:
    return SandboxState.parse_obj(state)
