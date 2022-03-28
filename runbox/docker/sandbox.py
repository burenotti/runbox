import aiohttp
import asyncio
from pydantic import BaseModel, Field
from aiodocker.containers import DockerContainer
from datetime import datetime
from typing import Any, Protocol
from runbox.docker.exceptions import SandboxError


class SandboxState(BaseModel):
    status: str = Field(..., alias="Status")
    exit_code: int | None = Field(None, alias="ExitCode")
    started_at: datetime = Field(..., alias="StartedAt")
    finished_at: datetime | None = Field(None, alias="FinishedAt")
    memory_limit: bool = Field(..., alias="OOMKilled")
    cpu_limit: bool = Field(..., alias="CpuLimit")


class Sandbox(Protocol):

    async def run(self, stdin: bytes | None = None):
        ...

    async def wait(self, timeout: float = None):
        ...

    async def state(self) -> SandboxState:
        ...


class SandboxInput(Protocol):

    async def send_bytes(self, send: bytes, compress: int | None = None) -> None:
        ...


class SandboxOutput(Protocol):

    async def receive_bytes(self, *, timeout: float | None = None) -> bytes:
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
        self._timeout_task: asyncio.Task | None = None
        self._input: aiohttp.ClientWebSocketResponse | None = None
        self._output: aiohttp.ClientWebSocketResponse | None = None

    async def wait(self):
        try:
            if self._timeout_task is None:
                raise SandboxError("Sandbox is not running")

            await self._timeout_task

        except TimeoutError:
            await self._container.kill()

    async def set_timeout(self):
        loop = asyncio.get_running_loop()
        waiter = self._container.wait(self._timeout)
        self._timeout_task = loop.create_task(waiter)

    def __await__(self):
        return self.wait().__await__()

    async def run(self) -> tuple[SandboxInput, SandboxOutput]:
        await self._container.start()

        sandbox_input: aiohttp.ClientWebSocketResponse
        sandbox_output: aiohttp.ClientWebSocketResponse

        sandbox_input = await self._container.websocket(
            stdout=True, stderr=True, stream=True,
        )

        sandbox_output = await self._container.websocket(
            stdin=True, stream=True,
        )

        self._input = sandbox_input
        self._output = sandbox_output

        return sandbox_input, sandbox_output

    async def state(self) -> SandboxState:
        container_info = await self._container.docker.get(self._container.id)
        state = container_info._container['State']
        state["CpuLimit"] = getattr(self._timeout_task, 'cancelled', False)
        return create_sandbox_state(state)


def create_sandbox_state(state: dict[str, Any]) -> SandboxState:
    return SandboxState.parse_obj(state)
