from datetime import timedelta
from typing import Awaitable, Callable, Literal, Sequence
from aiodocker import Docker
from aiodocker.volumes import DockerVolume
from aiodocker.exceptions import DockerError
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass


@asynccontextmanager
async def workdir(
    docker_client: Docker,
    name: str,
    driver: str = 'local',
):
    volume = None
    try:
        volume = await docker_client.volumes.create({
            'Name': name,
            'Driver': driver,
            'Labels': [],
        })

        yield volume
    finally:
        with suppress(DockerError):
            if volume:
                await volume.delete()


@dataclass
class DockerProfile:
    image: str
    workdir_mount: str
    cmd: Sequence[str]


@dataclass
class File:
    name: str
    content: str | bytes
    type: Literal["binary", "text"] = "text"

    def content_bytes(self):
        if self.type == 'binary':
            return self.content
        else:
            return self.content.encode('utf-8')

@dataclass(frozen=True)
class Limits:

    time: timedelta = timedelta(seconds=1)
    memory_mb: int = 64
    cpu_count: int = 1
    disk_space_mb: int = 256


class DockerExecutor:

    def __init__(self, url: str, name_factory: Callable[[], str]) -> None:
        self.docker_client = Docker(url)
        self.name_factory = name_factory

    async def run(
        self,
        profile: DockerProfile,
        files: Sequence[File],
        workdir: DockerVolume,
        limits: Limits = Limits(),
    ) -> Awaitable:
        container = await self.docker_client.containers.create({
            'Image': profile.image,
            'Cmd': profile.cmd,
            'Volumes': {
                profile.workdir_mount: workdir.name
            },
        }, name=self.name_factory())

