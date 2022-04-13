import io
import time
import tarfile
import pathlib
from typing import Any, Sequence
from aiodocker.docker import DockerContainer
from runbox.models import *


__all__ = [
    'create_tarball',
    'write_files',
]


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
    """Transfers archived files to a docker container
    """
    tarball = create_tarball(files)
    await container.put_archive(str(directory), tarball.getvalue())


def create_ulimit(name: str, soft: Any, hard: Any) -> dict[str, Any]:
    return {'Name': name, 'Soft': soft, 'Hard': hard}


def ulimits(limits: Limits):
    return [
        create_ulimit(
            'cpu',
            int(limits.time.total_seconds()),
            int(limits.time.total_seconds())
        ),
    ]

