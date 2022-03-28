from typing import Protocol

from aiodocker.stream import Message

from runbox.models import SandboxState


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
