import asyncio
import uuid
from typing import Callable, Sequence
from aiodocker import Docker
from aiodocker.volumes import DockerVolume
from aiodocker.exceptions import DockerError
from contextlib import asynccontextmanager, suppress
from runbox.docker.sandbox import DockerSandbox
from runbox.models import File, Limits, DockerProfile
from .utils import write_files, ulimits

__all__ = [
    'DockerExecutor',
]


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
    ) -> DockerSandbox:

        config = {
            'Image': profile.image,
            'Cmd': profile.cmd(files),
            'Volumes': {
                workdir.name: {
                    'bind': str(profile.workdir_mount),
                    'mode': 'rw'
                }
            },
            'Memory': limits.memory_bytes,
            'WorkingDir': str(profile.workdir_mount),
            'User': profile.user,
            'AttachStdin': True,
            'AttachStdout': True,
            'AttachStderr': True,
            'Tty': False,
            'OpenStdin': True,
            'StdinOnce': False,
            'OomKillDisable': False,
        }
        name = self.name_factory()
        task = self.docker_client.containers.create(
            config, name=name)

        container = await asyncio.wait_for(task, timeout)

        await write_files(
            container=container,
            directory=profile.workdir_mount,
            files=files,
        )

        return DockerSandbox(name, container, limits.time.total_seconds())

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
