import importlib
from pathlib import Path
from typing import Type, Any, Protocol, TypeVar, Generic

from pydantic import BaseModel

from runbox.build_stages.pipeline import Pipeline
from runbox.build_stages.stages import BuildStage

__all__ = ['load_stages', 'PipelineLoader', 'JsonPipelineLoader']


class StageGetter(Protocol):

    def __call__(self, stage_name: str) -> Type[BuildStage]:
        ...


def load_stages(stages_map: dict[str, str]) -> dict[str, Type[BuildStage]]:
    stages: dict[str, Type[BuildStage]] = {}
    for stage_name, path in stages_map.items():
        module, class_ = path.split(':')
        stage = getattr(importlib.import_module(module), class_)
        stages[stage_name] = stage

    return stages


PipelineType = TypeVar('PipelineType', bound=Pipeline, covariant=True)


class PipelineLoader(Protocol[PipelineType]):

    @property
    def meta(self) -> dict[str, Any]:
        ...

    def load(self) -> PipelineType:
        ...


T = TypeVar('T')

JsonBuildGroupSchema = dict[str, dict[str, Any]]


class JsonPipelineSchema(BaseModel):
    meta: dict[str, Any] = {}
    pipeline: dict[str, JsonBuildGroupSchema]


class JsonPipelineLoader(Generic[PipelineType]):

    def __init__(self, path: Path, class_: Type[PipelineType], stage_getter: StageGetter):
        self.stage_getter = stage_getter
        self.path = path
        self.class_ = class_
        self._schema: list[tuple[str, Type[BuildStage], BaseModel]] = []
        self._meta: dict[str, Any] = {}
        self.load_schema()

    @property
    def meta(self) -> dict[str, Any]:
        return self._meta

    def load_schema(self) -> None:
        data = JsonPipelineSchema.parse_file(self.path)
        self._meta = data.meta

        for group_name, group in data.pipeline.items():
            for stage_name, raw_params in group.items():
                stage = self.stage_getter(stage_name)
                params = stage.Params.parse_obj(raw_params)
                self._schema.append((group_name, stage, params))

    def load(self) -> PipelineType:
        pipeline = self.class_()
        for group, Stage, params in self._schema:
            pipeline.add_stages(group, Stage(params))

        return pipeline
