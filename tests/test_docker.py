from datetime import datetime, timedelta
import io
import tarfile
import aiodocker
import pytest

from runbox.docker import DockerExecutor
from runbox.docker.utils import create_tarball
from runbox.models import DockerProfile, File, Limits


@pytest.mark.asyncio
@pytest.fixture
async def docker_client():
    client = aiodocker.Docker()
    yield client
    await client.close()


@pytest.fixture
async def docker_executor():
    return DockerExecutor()


@pytest.fixture
def python_sandbox_profile():
    return DockerProfile(
        image='python-sandbox:latest',
        workdir_mount='/sandbox',
        user='sandbox',
        exec='python'
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
            workdir=workdir,
        )

        await docker_executor.run(container)
        await container.wait(timeout=5)
        logs = await container.log(stdout=True)
        assert logs == ['Hello, World!\n']


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
            workdir=workdir,
        )
        await container.start()
        await container.wait()
        container = await docker_client.containers.get(container.id)
        state = container._container['State']
        oom_killed = state['OOMKilled']
        assert oom_killed, 'Must be killled because of out of memory'
