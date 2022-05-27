from typing import Sequence, AsyncIterable

from runbox import DockerExecutor, Mount
from runbox.models import File, DockerProfile, Limits

__all__ = ['execute']


async def execute(
    profile: DockerProfile,
    files: Sequence[File],
    executor: DockerExecutor | None = None,
    stdin: bytes = b'',
    limits: Limits = Limits(),
    mounts: list[Mount] = None,
    attach_stdout: bool = True,
    attach_stderr: bool = True,
) -> AsyncIterable[str]:
    need_to_close_executor = False
    stdout = 1
    stderr = 2
    if executor is None:
        need_to_close_executor = True
        executor = DockerExecutor()

    sandbox = await executor.create_container(profile, files, mounts, limits)

    async with sandbox:
        io = await sandbox.run(stdin=stdin)
        while message := await io.read_out():
            if (message.stream == stdout and attach_stdout) or \
               (message.stream == stderr and attach_stderr):
                yield message.data.decode()
        await sandbox.wait()

    if need_to_close_executor:
        await executor.close()
