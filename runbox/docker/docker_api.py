import asyncio
import io
import pathlib
import tarfile
import uuid
import time
from datetime import timedelta
from typing import Awaitable, Callable, Literal, Sequence
from aiodocker import Docker
from aiodocker.containers import DockerContainer
from aiodocker.volumes import DockerVolume
from aiodocker.exceptions import DockerError
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass

__all__ = [
    'DockerProfile',
    'File',
    'Limits',
    'DockerExecutor',
]


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


@dataclass
class DockerProfile:
    image: str
    workdir_mount: str
    cmd: list[str]


@dataclass(frozen=True)
class Limits:
    time: timedelta = timedelta(seconds=1)
    memory_mb: int = 64
    cpu_count: int = 1
    disk_space_mb: int = 256


def create_tarball(files: Sequence[File]) -> io.BytesIO:
    file_obj = io.BytesIO()
    timestamp = time.time()
    with tarfile.open(fileobj=file_obj, mode='w') as tarball:
        for file in files:
            content = file.content_bytes()

            file_info = tarfile.TarInfo(file.name)
            file_info.size = len(content)
            file_info.mtime = timestamp

            tarball.addfile(
                tarinfo=file_info,
                fileobj=io.BytesIO(content)
            )

    return file_obj


async def write_files(
    container: DockerContainer,
    directory: pathlib.Path,
    files: Sequence[File],
) -> None:
    tarball = create_tarball(files)
    await container.put_archive(directory, tarball.getvalue())


class DockerExecutor:

    def __init__(
        self,
        url: str = None,
        name_factory: Callable[[], str] = None
    ) -> None:
        self.docker_client = Docker(url)
        if name_factory:
            self.name_factory = name_factory
        else:
            self.name_factory = lambda: str(uuid.uuid4())

    async def create_container(
        self,
        profile: DockerProfile,
        files: Sequence[File],
        workdir: DockerVolume,
        limits: Limits = Limits(),
        timeout: int = 5
    ) -> DockerContainer:

        config = {
            'Image': profile.image,
            'Cmd': profile.cmd,
            'Volumes': {
                workdir.name: {
                     'bind': profile.workdir_mount,
                     'mode': 'rw'
                }
            },
            'WorkingDir': profile.workdir_mount,
            'User': 'sandbox',
            'AttachStdin': True,
            'AttachStdout': True,
            'AttachStderr': True,
            'Tty': False,
            'OpenStdin': True,
            'StdinOnce': True,
        }

        task = self.docker_client.containers.create(config, name=self.name_factory())

        container = await asyncio.wait_for(task, timeout)

        await write_files(
            container=container,
            directory=profile.workdir_mount,
            files=files,
        )

        return container

    async def run(self, container: DockerContainer):
        await container.start()

    @asynccontextmanager
    async def workdir(
        self,
        name: str = None,
        driver: str = 'local',
        timeout: int = 5,
    ):

        if not name:
            name = self.name_factory()

        volume = None
        try:
            volume = await asyncio.wait_for(self.docker_client.volumes.create({
                'Name': name,
                'Driver': driver,
            }), timeout)
            yield volume
        finally:
            if volume:
                with suppress(DockerError):
                    await volume.delete()

