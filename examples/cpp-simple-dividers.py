import asyncio
import pathlib
from datetime import timedelta
from typing import Sequence

from runbox import DockerExecutor
from runbox.models import DockerProfile, Limits, File


class BuildProfile(DockerProfile):
    image = 'gcc10-sandbox:latest'
    user: str = 'sandbox'
    workdir_mount: pathlib.Path = '/sandbox'
    exec: str = 'g++'

    def cmd(self, files: Sequence[File]) -> list[str]:
        return ['g++', *map(lambda file: file.name, files), '-o', '/sandbox/build']


class RunProfile(DockerProfile):
    image: str = 'ubuntu:latest'
    workdir_mount: pathlib.Path = '/opt'
    user: str = 'root'
    exec: str = 'g++'

    def cmd(self, _: Sequence[File]) -> list[str]:
        return ['/opt/build']


limits = Limits(time=timedelta(hours=1))

build_profile = BuildProfile()
run_profile = RunProfile()

with open('./src/dividers.cpp') as file:
    content = file.read()
    file = File(name='main.cpp', content=content)


async def main():
    executor = DockerExecutor()

    async with executor.workdir() as workdir:
        build_sandbox = await executor.create_container(build_profile, [file], workdir)
        await build_sandbox.run()
        await build_sandbox.wait()

        run_sandbox = await executor.create_container(run_profile, [], workdir)

        reader = await run_sandbox.run(stdin=b'354\n')
        await run_sandbox.wait()
        data = await reader.read_out()
        print(data.data)

    await executor.close()


asyncio.run(main())
