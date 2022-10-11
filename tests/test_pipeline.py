from pathlib import Path

from runbox.models import DockerProfile, Limits
from runbox.build_stages import DefaultExecutionPipeline
from runbox.build_stages.pipeline_loaders import (
    pipeline_from_yaml,
    _load_stages,
)
from runbox.build_stages.stages import UseSandbox, UseVolume


def test_can_load_default_stages():
    loaded_stages = _load_stages({
        'use_sandbox': 'runbox.build_stages.stages:UseSandbox',
        'use_volume': 'runbox.build_stages.stages:UseVolume',
    })

    expected_stages = {
        'use_sandbox': UseSandbox,
        'use_volume': UseVolume,
    }

    assert loaded_stages == expected_stages


def test_can_load_pipeline_from_yaml():
    pipeline = pipeline_from_yaml(
        file=Path('../examples/src/python3.yml'),
        stages_map={
            'use_sandbox': 'runbox.build_stages.stages:UseSandbox',
        },
        class_=DefaultExecutionPipeline
    )

    expected_pipeline = DefaultExecutionPipeline([
        UseSandbox(
            UseSandbox.Params(
                key="sandbox",
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
    ])

    assert pipeline.stages[0].params == expected_pipeline.stages[0].params
