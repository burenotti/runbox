import asyncio
from pathlib import Path

from runbox import DockerExecutor
from runbox.build_stages import DefaultExecutionPipeline
from runbox.build_stages.pipeline_loaders import pipeline_from_yaml
from runbox.build_stages.stages import StreamType


class ConsoleObserver:

    @property
    async def stdin(self):
        yield

    async def write_output(self, key: str, data: str, stream: StreamType):
        print(f"{key}: {data}")


async def main():
    executor = DockerExecutor()

    pipeline = pipeline_from_yaml(
        file=Path('./src/python3.yml'),
        stages_map={
            'use_sandbox': 'runbox.build_stages.stages:UseSandbox',
        },
        class_=DefaultExecutionPipeline,
    )

    await pipeline.execute(executor, ConsoleObserver())

    await executor.close()


asyncio.run(main())
