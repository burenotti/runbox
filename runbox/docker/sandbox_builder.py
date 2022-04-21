from __future__ import annotations

from pathlib import Path

from aiodocker.volumes import DockerVolume

from .docker_api import DockerExecutor
from .mount import Mount
from .sandbox import DockerSandbox
from ..models import DockerProfile, Limits, File


class SandboxBuilder:

    def __init__(self):
        self._profile: DockerProfile | None = None
        self._limits: Limits | None = None
        self._files: list[File] = []
        self._mounts: list[Mount] = []

    def with_limits(self, limits: Limits) -> SandboxBuilder:
        new_builder = self.copy()
        new_builder._limits = limits
        return new_builder

    def with_profile(self, profile: DockerProfile) -> SandboxBuilder:
        new_builder = self.copy()
        new_builder._profile = profile
        return new_builder

    def add_files(self, *files: File) -> SandboxBuilder:
        new_builder = self.copy()
        new_builder._files.extend(files)
        return new_builder

    def mount(
        self,
        volume: DockerVolume,
        bind: Path | str,
        readonly: bool = False,
    ) -> SandboxBuilder:
        new_builder = self.copy()
        new_builder._mounts.append(Mount(
            volume=volume,
            bind=bind,
            readonly=readonly
        ))
        return new_builder

    async def create(self, executor: DockerExecutor, timeout: int = 5) -> DockerSandbox:
        return await executor.create_container(
            profile=self._profile,
            files=self._files,
            mounts=self._mounts,
            limits=self._limits,
            timeout=timeout,
        )

    def copy(self) -> SandboxBuilder:
        new_builder = SandboxBuilder()
        # DockerProfile and Limits are immutable,
        # so copying is not necessary
        new_builder._profile = self._profile
        new_builder._limits = self._limits

        # Copying mounts and files only by links,
        # because Mount and File models are immutable
        new_builder._mounts = self._mounts[:]
        new_builder._files = self._files[:]

        return new_builder
