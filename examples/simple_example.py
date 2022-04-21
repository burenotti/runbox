import asyncio
from datetime import timedelta

import runbox
from runbox.models import (
    DockerProfile, Limits, File
)

profile = DockerProfile(
    image='python-sandbox:latest',
    workdir='/sandbox',
    cmd_template=["python", ...],
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
        builder = runbox.SandboxBuilder()

        container = await builder \
            .with_profile(profile) \
            .with_limits(limits) \
            .add_files(file) \
            .mount(workdir, '/sandbox') \
            .create(executor)

        # Context manager will automatically remove container on exit
        async with container as sandbox:
            # sandbox.run returns object, that gives you a way to
            # communicate with container via io.read_out and io.write_in methods
            io = await sandbox.run(stdin=b'John\n')
            # Wait until the container stops or is killed due to the timeout
            await sandbox.wait()
            message = await io.read_out()
            text = message.data.decode('utf-8')
            print(text)

    await executor.close()


if __name__ == '__main__':
    asyncio.run(main())
