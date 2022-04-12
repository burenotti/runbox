import asyncio
from datetime import timedelta

import runbox
from runbox.models import (
    DockerProfile, Limits, File
)

profile = DockerProfile(
    image='python-sandbox:latest',
    workdir_mount='/sandbox',
    exec='python',
    user='sandbox'
)

limits = Limits(
    time=timedelta(seconds=3),
    memory_mb=64,
)

file = File(
    name='main.py',
    content='name = input("What is your name?\\n")\n'
            'print(f"Hello, {name}")'
)


async def main():
    executor = runbox.DockerExecutor()

    # Workdir is a temporary volume, that provides you a way to share data between a couple of containers
    # Volume will be deleted upon exiting the context manager
    async with executor.workdir() as workdir:
        container = await executor.create_container(
            profile=profile,
            limits=limits,
            files=[file],
            workdir=workdir
        )

        # Context manager will automatically remove container on exit
        async with container as sandbox:
            await sandbox.run(stdin=b'John\n')
            # Wait until the container stops or is killed due to the timeout
            await sandbox.wait()
            logs = await sandbox.log(stdout=True)

            print(logs)

    await executor.close()


if __name__ == '__main__':
    asyncio.run(main())
