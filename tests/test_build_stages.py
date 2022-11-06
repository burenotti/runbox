from pathlib import Path
from typing import AsyncIterable

import pytest
from aiodocker import DockerError

from runbox import DockerExecutor
from runbox.build_stages import UseSandbox, BasePipeline, BuildState
from runbox.build_stages.exceptions import NonZeroExitCodeError, MemoryLimitError, CpuLimitError
from runbox.build_stages.stages import StreamType, LoadableFile
from runbox.models import DockerProfile, Limits


class TestSandboxObserver:

    def __init__(
        self,
        stdin: list[str] = None,
        expected_stdout: str = '',
        expected_stderr: str = '',
    ):
        self._stdin = stdin or []
        self.expected_stdout = expected_stdout
        self.expected_stderr = expected_stderr
        self.actual_stdout: list[str] = []
        self.actual_stderr: list[str] = []

    @property
    async def stdin(self) -> AsyncIterable[str]:
        for chunk in self._stdin:
            yield chunk

    async def write_output(self, key: str, data: str, stream: StreamType):
        if stream == StreamType.stdout:
            self.actual_stdout.append(data)
        elif stream == StreamType.stderr:
            self.actual_stderr.append(data)

    def validate(self):
        actual_stdout = ''.join(self.actual_stdout)
        actual_stderr = ''.join(self.actual_stderr)

        assert actual_stdout == self.expected_stdout
        assert actual_stderr == self.expected_stderr


def pipeline() -> BasePipeline:
    return BasePipeline() \
        .add_stages(
        "run",
        UseSandbox(UseSandbox.Params(
            key='sandbox',
            profile=DockerProfile(
                image='sandbox:python-3.10',
                cmd_template=['python', 'main.py'],
                user='sandbox',
                workdir=Path('/sandbox'),
            ),
            files=[
                LoadableFile(
                    name='main.py',
                    content='print("Hello, world!")\n'
                )
            ],
            limits=Limits(),
            mounts=[],
            attach=False
        ))
    )


@pytest.fixture
@pytest.mark.asyncio
async def executor():
    executor = DockerExecutor()
    yield executor
    await executor.close()


@pytest.mark.asyncio
async def test_useSandbox_can_run_sandbox(executor):
    state = BuildState(
        executor=executor,
        shared={},
        observer=None,
    )

    stage = UseSandbox(UseSandbox.Params(
        key='sandbox',
        profile=DockerProfile(
            image='sandbox:python-3.10',
            cmd_template=['python', 'main.py'],
            user='sandbox',
            workdir=Path('/sandbox'),
        ),
        files=[
            LoadableFile(
                name='main.py',
                content='print("Hello, world!")\n'
            )
        ],
        limits=Limits(),
        mounts=[],
        attach=False
    ))

    await stage.setup(state)
    logs = await stage._sandbox.log(stdout=True)
    state = await stage._sandbox.state()
    assert state.exit_code == 0
    assert logs == ['Hello, world!\n']
    await stage.dispose()

    try:
        await stage._sandbox.state()
        assert False, "Can't retrieve state if container deleted"
    except DockerError:
        assert True


@pytest.mark.asyncio
async def test_useSandbox_correctly_observes_output(executor):
    observer = TestSandboxObserver(
        stdin=[],
        expected_stdout='Hello, world!\n',
        expected_stderr='',
    )
    state = BuildState(
        executor=executor,
        shared={},
        observer=observer,
    )

    stage = UseSandbox(UseSandbox.Params(
        key='sandbox',
        profile=DockerProfile(
            image='sandbox:python-3.10',
            cmd_template=['python', 'main.py'],
            user='sandbox',
            workdir=Path('/sandbox'),
        ),
        files=[
            LoadableFile(
                name='main.py',
                content='print("Hello, world!")\n'
            )
        ],
        limits=Limits(),
        mounts=[],
        attach=True,
    ))

    await stage.setup(state)
    await stage.dispose()
    observer.validate()


@pytest.mark.asyncio
async def test_useSandbox_raises_on_nonzero_exitcode(executor):
    state = BuildState(
        executor=executor,
        shared={}
    )
    stage = UseSandbox(UseSandbox.Params(
        key='sandbox',
        profile=DockerProfile(
            image='sandbox:python-3.10',
            cmd_template=['python', 'main.py'],
            user='sandbox',
            workdir=Path('/sandbox'),
        ),
        files=[
            LoadableFile(
                name='main.py',
                content='Счёт древних шизов'  # Provides syntax error,
            )
        ],
        limits=Limits(),
        mounts=[],
        attach=False,
    ))

    with pytest.raises(NonZeroExitCodeError):
        await stage.setup(state)

    await stage.dispose()


@pytest.mark.asyncio
async def test_useSandbox_raises_on_memory_limit(executor):
    state = BuildState(
        executor=executor,
        shared={}
    )
    stage = UseSandbox(UseSandbox.Params(
        key='sandbox',
        profile=DockerProfile(
            image='sandbox:python-3.10',
            cmd_template=['python', 'main.py'],
            user='sandbox',
            workdir=Path('/sandbox'),
        ),
        files=[
            LoadableFile(
                name='main.py',
                content='a = [i for i in range(10**10)]'  # Provides memory limit,
            )
        ],
        limits=Limits(
            memory_mb=256,
        ),
        mounts=[],
        attach=False,
    ))

    with pytest.raises(MemoryLimitError):
        await stage.setup(state)

    await stage.dispose()

@pytest.mark.asyncio
async def test_useSandbox_raises_on_cpu_limit(executor):
    state = BuildState(
        executor=executor,
        shared={}
    )
    stage = UseSandbox(UseSandbox.Params(
        key='sandbox',
        profile=DockerProfile(
            image='sandbox:python-3.10',
            cmd_template=['python', 'main.py'],
            user='sandbox',
            workdir=Path('/sandbox'),
        ),
        files=[
            LoadableFile(
                name='main.py',
                content='import time; time.sleep(100)'  # Provides cpu limit,
            )
        ],
        limits=Limits(),
        mounts=[],
        attach=False,
    ))

    with pytest.raises(CpuLimitError):
        await stage.setup(state)

    await stage.dispose()
