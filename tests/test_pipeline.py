from pathlib import Path

import pytest

from runbox import DockerExecutor
from runbox.build_stages import BasePipeline, CompileAndRunPipeline
from runbox.build_stages.pipeline_loaders import (
    load_stages, JsonPipelineLoader,
)
from runbox.build_stages.stages import (
    UseSandbox, UseVolume,
    default_stages, LoadableFile
)
from runbox.models import DockerProfile, Limits
from test_build_stages import TestSandboxObserver  # type: ignore
from test_docker import docker_executor


@pytest.fixture
def hello_world_observer():
    return TestSandboxObserver(expected_stdout="Hello, world!\n")


def test_can_load_default_stages():
    loaded_stages = load_stages({
        'use_sandbox': 'runbox.build_stages.stages:UseSandbox',
        'use_volume': 'runbox.build_stages.stages:UseVolume',
    })

    expected_stages = {
        'use_sandbox': UseSandbox,
        'use_volume': UseVolume,
    }

    assert loaded_stages == expected_stages


def test_can_load_pipeline_from_json():
    pipeline = JsonPipelineLoader(
        path=Path('./tests/python3.json'),
        stage_getter=lambda stage: load_stages(default_stages())[stage],
    ).fill(BasePipeline())

    expected_pipeline = BasePipeline() \
        .add_stages(
        "run",
        UseSandbox(
            UseSandbox.Params(
                key="python",
                files=[
                    LoadableFile(
                        name="main.py",
                        content="print('Hello, world!')"
                    )
                ],
                profile=DockerProfile(
                    image='sandbox:python-3.10',
                    workdir=Path('/sandbox'),
                    cmd_template=["python", "main.py"],
                    user='sandbox'
                ),
                limits=Limits(),
                attach=True,
            )
        )
    )

    expected_params = expected_pipeline._groups['run'].stages[0].params
    actual_params = pipeline._groups['run'].stages[0].params
    assert actual_params == expected_params


@pytest.mark.asyncio
async def test_pipeline_can_run_and_observe_code(
    docker_executor: DockerExecutor,
    hello_world_observer: TestSandboxObserver,
):
    pipeline = JsonPipelineLoader(
        path=Path('./tests/python3_simplified.json'),
        stage_getter=lambda stage: load_stages(default_stages())[stage],
    ).fill(BasePipeline())

    pipeline.with_executor(docker_executor)
    pipeline.with_observer(hello_world_observer)
    await pipeline.execute_group('run')

    hello_world_observer.validate()


@pytest.mark.asyncio
async def test_pipeline_multistage_build(
    docker_executor: DockerExecutor,
):
    observer = TestSandboxObserver(stdin=['35\n'], expected_stdout='5 7 ')
    pipeline = (
        JsonPipelineLoader(
            path=Path('./tests/gcc_multistage.json'),
            stage_getter=lambda stage: load_stages(default_stages())[stage],
        )
        .fill(CompileAndRunPipeline())
        .with_executor(docker_executor)
        .with_observer(observer)
    )
    await pipeline.build()
    await pipeline.run()
    await pipeline.finalize()
    observer.validate()
