import importlib
from pathlib import Path
from typing import Type, Any

import yaml
from yaml.loader import SafeLoader

from runbox.build_stages.pipeline import ExecutionPipeline
from runbox.build_stages.stages import BuildStage

__all__ = ['parse_obj', 'pipeline_from_yaml']


def _load_stages(stages_map: dict[str, str]):
    stages: dict[str, Type[BuildStage]] = {}
    for stage_name, path in stages_map.items():
        module, class_ = path.split(':')
        stage = getattr(importlib.import_module(module), class_)
        stages[stage_name] = stage

    return stages


def parse_obj(
    stages_map: dict[str, Type[BuildStage]],
    obj: dict[str, Any],
) -> list[BuildStage]:
    stages = []
    for stages_schema in obj['pipeline']:
        stage_name, raw_params = next(iter(stages_schema.items()))
        stage = stages_map[stage_name]
        params = stage.Params.parse_obj(raw_params)
        stages.append(stage(params))
    return stages


def pipeline_from_yaml(
    file: Path,
    stages_map: dict[str, str],
    class_: Type[ExecutionPipeline]
) -> ExecutionPipeline:
    with file.open() as fp:
        data = yaml.load(fp, Loader=SafeLoader)

    pipeline = class_()
    pipeline.add_stages(*parse_obj(_load_stages(stages_map), data))
    return pipeline
