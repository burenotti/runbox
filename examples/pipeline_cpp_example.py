import asyncio
from pathlib import Path

from runbox import DockerExecutor
from runbox.build_stages import load_stages, JsonPipelineLoader, default_stages
from runbox.build_stages.pipeline import CompileAndRunPipeline
from runbox.build_stages.stages import StreamType


class ConsoleObserver:

    @property
    async def stdin(self):
        yield 'John\n'

    async def write_output(self, key: str, data: str, stream: StreamType):
        print(f"{key}: {data}")


def get_stage(name: str):
    return load_stages(default_stages())[name]


async def main():
    executor = DockerExecutor()

    builder = JsonPipelineLoader[CompileAndRunPipeline](
        path=Path('./src/cpp.json'),
        class_=CompileAndRunPipeline,
        stage_getter=get_stage
    )

    pipeline = builder.load()
    pipeline.with_executor(executor)
    pipeline.with_observer(ConsoleObserver())

    await pipeline.build()
    await pipeline.run()
    await pipeline.finalize()
    await executor.close()


asyncio.run(main())
