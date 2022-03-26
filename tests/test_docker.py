import io
import tarfile
import aiodocker
import pytest

from runbox.docker.docker_api import(
   DockerExecutor, create_tarball, File
)


@pytest.mark.asyncio
@pytest.fixture
async def docker_client():
    client = aiodocker.Docker()
    yield client
    await client.close()


@pytest.fixture
async def docker_executor():
    return DockerExecutor()


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

