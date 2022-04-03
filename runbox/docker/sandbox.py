import asyncio
from typing import Any
from contextlib import suppress

import aiodocker
from aiodocker.containers import DockerContainer
from aiodocker.stream import Stream

from runbox.docker.exceptions import SandboxError
from runbox.models import SandboxState
from runbox.proto import SandboxIO


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
            with suppress(aiodocker.DockerError):
                await self.kill()
                self._cpu_limit = True
        finally:
            self._timeout_task = None

    async def set_timeout(self):
        loop = asyncio.get_running_loop()
        waiter = self._container.wait(timeout=self._timeout)

        if self._timeout_task is not None:
            raise SandboxError("Container is already running")

        self._timeout_task = loop.create_task(waiter)

    async def run(self, stdin: bytes | None = None) -> SandboxIO:
        self._cpu_limit = False

        await self._container.start()

        stream = self._container.attach(
            stdin=True, stdout=True, stderr=True
        )
        self._stream = stream

        if stdin:
            await stream.write_in(stdin)

        await self.set_timeout()

        return stream

    async def state(self) -> SandboxState:
        container_info = await self._container.docker.containers.get(self._container.id)
        state = container_info._container['State']

        state = {**state, 'CpuLimit': self._cpu_limit}
        return create_sandbox_state(state)

    async def log(self, stdout: bool = False, stderr: bool = False) -> list[str]:
        return await self._container.log(stdout=stdout, stderr=stderr)

    async def kill(self) -> None:
        await self._container.kill()

    async def delete(self, force: bool = False) -> None:
        await self._container.delete(force=force)

    def __await__(self):
        return self.wait().__await__()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.delete()


def create_sandbox_state(state: dict[str, Any]) -> SandboxState:
    return SandboxState.parse_obj(state)
