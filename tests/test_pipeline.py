from pathlib import Path

from runbox.build_stages import BasePipeline
from runbox.build_stages.pipeline_loaders import (
    load_stages, JsonPipelineLoader,
)
from runbox.build_stages.stages import UseSandbox, UseVolume, default_stages
from runbox.models import DockerProfile, Limits, File


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
    pipeline: BasePipeline = JsonPipelineLoader[BasePipeline](
        path=Path('./tests/python3.json'),
        stage_getter=lambda stage: load_stages(default_stages())[stage],
        class_=BasePipeline
    ).load()

    expected_pipeline = BasePipeline() \
        .add_stages(
        "run",
        UseSandbox(
            UseSandbox.Params(
                key="python",
                files=[
                    File(
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

    assert pipeline._groups['run'][0].params == expected_pipeline._groups['run'][0].params
