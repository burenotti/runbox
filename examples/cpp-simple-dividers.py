import asyncio
from datetime import timedelta

from runbox import DockerExecutor, SandboxBuilder
from runbox.models import DockerProfile, Limits, File

limits = Limits(time=timedelta(hours=1))

build_profile = DockerProfile(
    image='gcc10-sandbox:latest',
    user='sandbox',
    workdir='/sandbox',
    cmd_template=['g++', ..., '-o', '/sandbox/build']
)
run_profile = DockerProfile(
    image='ubuntu:latest',
    user='root',
    workdir='/opt',
    cmd_template=['/opt/build']
)

with open('./src/dividers.cpp') as file:
    content = file.read()
    file = File(name='main.cpp', content=content)


async def main():
    executor = DockerExecutor()

    async with executor.workdir() as workdir:
        builder = SandboxBuilder() \
            .with_limits(limits) \
            .add_files(file)

        build_sandbox = await builder \
            .with_profile(build_profile) \
            .mount(workdir, '/sandbox') \
            .create(executor)

        await build_sandbox.run()
        await build_sandbox.wait()

        run_sandbox = await builder \
            .with_profile(run_profile) \
            .mount(workdir, '/opt') \
            .create(executor)

    reader = await run_sandbox.run(stdin=b'354\n')
    await run_sandbox.wait()
    data = await reader.read_out()
    print(data.data)

    await executor.close()


asyncio.run(main())
