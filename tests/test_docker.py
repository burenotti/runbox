import aiodocker
import pytest

from runbox.docker.docker_api import workdir


@pytest.mark.asyncio
@pytest.fixture
async def docker_client():
    return aiodocker.Docker()


@pytest.mark.asyncio
async def test_workdir(docker_client: aiodocker.Docker):
    async with workdir(docker_client, 'test-volume') as wd:
        volumes = await docker_client.volumes.list()
        volume_names = [vol["Name"] for vol in volumes["Volumes"]]

        assert wd.name == 'test-volume'
        assert wd.name in volume_names

    # after leaving context volume must be deleted

    volumes = await docker_client.volumes.list()
    volume_names = [vol["Name"] for vol in volumes["Volumes"]]
    assert wd.name not in volume_names
