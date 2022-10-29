import io
import tarfile
from datetime import timedelta
from pathlib import Path

import aiodocker
import pytest
from aiodocker import DockerError

from runbox.docker import DockerExecutor
from runbox.docker.mount import Mount
from runbox.docker.utils import create_tarball
from runbox.models import DockerProfile, File, Limits


@pytest.mark.asyncio
@pytest.fixture
async def docker_client():
    client = aiodocker.Docker()
    yield client
    await client.close()


@pytest.mark.asyncio
@pytest.fixture
async def docker_executor():
    executor = DockerExecutor()
    yield executor
    await executor.close()


@pytest.fixture
def python_sandbox_profile():
    return DockerProfile(
        image='sandbox:python-3.10',
        workdir=Path('/sandbox'),
        user='sandbox',
        cmd_template=["python", ...]
    )


@pytest.fixture
def python_code_sample():
    return [
        File(
            name='main.py',
            content=(
                r'print(f"Hello, World!")'
            )
        )
    ]


@pytest.mark.asyncio
async def test_workdir(docker_executor: DockerExecutor, docker_client: aiodocker.Docker):
    async with docker_executor.workdir('test-volume') as wd:
        volumes = await docker_client.volumes.list()
        volume_names = [vol["Name"] for vol in volumes["Volumes"]]

        assert wd.name == 'test-volume'
        assert wd.name in volume_names

    # after leaving context volume must be deleted

    volumes = await docker_client.volumes.list()
    volume_names = [vol["Name"] for vol in volumes["Volumes"]]
    assert wd.name not in volume_names


def test_tarball_create_single_file():
    files = [
        File(
            name='main.py',
            content=(
                'print("Hello, world!")'
            )
        )
    ]

    tar_file = create_tarball(files)
    fileobj = io.BytesIO(tar_file.getvalue())

    with tarfile.open(fileobj=fileobj, mode='r') as tarball:
        assert tarball.getnames() == ['main.py']
        data = tarball.extractfile('main.py').read().decode('utf-8')
        assert data == 'print("Hello, world!")'


def test_tarball_create_multiple_files():
    files = [
        File(
            name='main.py',
            content=(
                'print("Hello, world!")'
            )
        ),
        File(
            name='input.txt',
            content=(
                'important text!'
            )
        )
    ]

    tar_file = create_tarball(files)
    fileobj = io.BytesIO(tar_file.getvalue())

    with tarfile.open(fileobj=fileobj, mode='r') as tarball:
        assert tarball.getnames() == ['main.py', 'input.txt']
        main_py = tarball.extractfile('main.py').read().decode('utf-8')
        input_txt = tarball.extractfile('input.txt').read().decode('utf-8')
        assert main_py == 'print("Hello, world!")'
        assert input_txt == 'important text!'


@pytest.mark.asyncio
async def test_code_running_no_input(
    docker_client: aiodocker.Docker,
    python_sandbox_profile: DockerProfile,
    python_code_sample: list[File],
    docker_executor: DockerExecutor,
):
    async with docker_executor.workdir() as workdir:
        container = await docker_executor.create_container(
            profile=python_sandbox_profile,
            files=python_code_sample,
            mounts=[
                Mount(
                    volume=workdir,
                    bind=Path('/sandbox'),
                    readonly=False,
                )
            ],
        )

        async with container:
            await container.run()
            await container.wait()
            logs = await container.log(stdout=True)
    assert logs[0] in ('Hello, World!\r\n', 'Hello, World!\n')


@pytest.mark.asyncio
async def test_code_running_with_input(
    docker_client: aiodocker.Docker,
    python_sandbox_profile: DockerProfile,
    docker_executor: DockerExecutor,
):
    files = [
        File(
            name='main.py',
            content=(
                'name = input("What is your name?\\n")\n'
                r'print(f"Hello, {name}")'
            )
        )
    ]

    limits = Limits(time=timedelta(seconds=2))

    async with docker_executor.workdir() as workdir:
        container = await docker_executor.create_container(
            profile=python_sandbox_profile,
            files=files,
            mounts=[
                Mount(
                    volume=workdir,
                    bind=Path('/sandbox'),
                    readonly=False,
                )
            ],
            limits=limits,
        )

        stdin = await container.run()
        async with container:
            await stdin.write_in(b'Andrew\n')
            await container.wait()
            logs = await container.log(stdout=True)
            state = await container.state()

    assert not state.cpu_limit and not state.memory_limit, state.duration
    assert logs == ['What is your name?\n', 'Hello, Andrew\n']


@pytest.mark.asyncio
async def test_code_running_oom_kill(
    docker_client: aiodocker.Docker,
    docker_executor: DockerExecutor,
    python_sandbox_profile,
):
    async with docker_executor.workdir() as workdir:
        container = await docker_executor.create_container(
            profile=python_sandbox_profile,
            files=[
                # allocating an array of an 10^9 elements must provide memory limit
                File(name='main.py', content='a = [i for i in range(10**9)]')
            ],
            limits=Limits(
                memory_mb=64
            ),
            mounts=[Mount(
                volume=workdir,
                bind=Path('/sandbox'),
                readonly=False,
            )]
        )
        async with container:
            await container.run()
            await container.wait()
            state = await container.state()
        assert state.memory_limit


@pytest.mark.asyncio
async def test_code_timeout_kill(
    docker_client: aiodocker.Docker,
    docker_executor: DockerExecutor,
    python_sandbox_profile,
):
    async with docker_executor.workdir() as workdir:
        container = await docker_executor.create_container(
            profile=python_sandbox_profile,
            files=[
                File(
                    name='main.py',
                    content=(
                        'while True:\n'
                        '    print("Hello, world!")'
                    ),
                )
            ],
            limits=Limits(
                time=timedelta(seconds=3),
                memory_mb=64,
            ),
            mounts=[Mount(
                volume=workdir,
                bind=Path('/sandbox'),
                readonly=False,
            )],
        )
        async with container:
            await container.run()
            await container.wait()
            state = await container.state()
    assert state.cpu_limit, 'Must be killed because of timeout'


@pytest.mark.asyncio
async def test_can_create_container_with_profile_specifying_only_image(
    docker_executor: DockerExecutor,
    docker_client: aiodocker.Docker,
):
    try:
        await docker_client.images.inspect('alpine:latest')
        has_image = True
    except DockerError:
        has_image = False

    if not has_image:
        await docker_client.images.pull('alpine:latest')

    sandbox = await docker_executor.create_container(
        profile=DockerProfile(image="alpine:latest")
    )

    container = await docker_client.containers.create({
        "Image": "alpine:latest",
    })

    expected_info = (await container.show())['Config']

    info = (await sandbox._container.show())['Config']

    await sandbox.delete()
    await container.delete()

    assert expected_info["Cmd"] == info["Cmd"]
    assert expected_info["WorkingDir"] == info["WorkingDir"]
    assert expected_info["User"] == info["User"]
