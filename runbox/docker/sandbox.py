import asyncio
from contextlib import suppress
from pathlib import Path
from typing import Any

import aiodocker
from aiodocker.containers import DockerContainer
from aiodocker.stream import Stream, Message

from runbox.docker.exceptions import SandboxError
from runbox.docker.utils import write_files
from runbox.models import SandboxState, File
from runbox.proto import SandboxIO


class StreamWrapper:

    def __init__(self, stream: Stream, detach_keys: str = "ctrl-c"):
        self.stream = stream
        self.detach_keys = detach_keys

    async def write_in(self, data: bytes) -> None:
        await self.stream.write_in(data)

    async def read_out(self) -> Message | None:
        return await self.stream.read_out()

    async def detach(self) -> None:
        await self.stream.write_in(self.detach_keys.encode())


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
        self._stream: StreamWrapper | None = None

    @property
    def stream(self) -> SandboxIO | None:
        assert self._stream is not None, "Stream can't be get before the container is started"
        return StreamWrapper(self._stream)

    async def write_files(self, path: Path | str, *files: File) -> None:
        await write_files(self._container, Path(path), files)

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

    async def run(self, stdin: bytes | None = None) -> StreamWrapper:
        self._cpu_limit = False

        await self._container.start()

        stream = self._container.attach(
            stdin=True, stdout=True, stderr=True, logs=True,
            detach_keys="ctrl-c"
        )
        self._stream = StreamWrapper(stream)

        if stdin:
            await stream.write_in(stdin)

        await self.set_timeout()

        return StreamWrapper(stream)

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
