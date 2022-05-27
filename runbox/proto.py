from typing import Protocol, TYPE_CHECKING

from aiodocker.stream import Message

from runbox.models import SandboxState, File

if TYPE_CHECKING:
    from runbox.docker.docker_api import DockerExecutor


class SandboxInput(Protocol):

    async def write_in(self, send: bytes) -> None:
        ...


class SandboxOutput(Protocol):

    async def read_out(self) -> Message | None:
        ...


class SandboxIO(SandboxInput, SandboxOutput, Protocol):
    ...


class Sandbox(Protocol):

    stream: SandboxIO | None

    async def write_files(self, *file: File) -> None:
        ...

    async def run(self, stdin: bytes | None = None) -> SandboxIO:
        ...

    async def wait(self, timeout: float = None):
        ...

    async def state(self) -> SandboxState:
        ...

    async def log(self, stdout: bool = False, stderr: bool = False) -> list[str]:
        ...

    async def kill(self) -> None:
        ...

    async def delete(self, force: bool = False) -> None:
        ...

    async def __aenter__(self):
        ...

    async def __aexit__(self, *_):
        ...


class SandboxFactory(Protocol):

    async def create(self, executor: "DockerExecutor") -> Sandbox:
        ...
