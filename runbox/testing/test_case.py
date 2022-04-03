from .proto import TestResult, TestStatus
from ..models import SandboxState
from ..proto import Sandbox, SandboxIO


class IOTestCase:

    def __init__(
        self,
        stdin: bytes | None = None,
        expected_stout: bytes | None = None,
        expected_stderr: bytes | None = None,
        encoding: str = 'utf-8',
    ):
        self.expected_stout = expected_stout or b''
        self.expected_stderr = expected_stderr or b''
        self.stdin = stdin
        self.encoding = encoding

    async def exec(self, sandbox: Sandbox) -> TestResult:

        reader = await sandbox.run(self.stdin)

        await sandbox.wait()

        stdout, stderr = await self._read_output(reader)

        state = await sandbox.state()

        return self._check(stdout, stderr, state)

    @staticmethod
    async def _read_output(reader: SandboxIO) -> tuple[bytes, bytes]:
        stdout = b''
        stderr = b''
        while message := await reader.read_out():
            if message.stream == 1:
                stdout += message.data
            elif message.stream == 2:
                stderr += message.data

        return stdout, stderr

    def _check(self, stdout: bytes, stderr: bytes, state: SandboxState) -> TestResult:
        if (
            stdout == self.expected_stderr or not self.expected_stout and
            stderr == self.expected_stderr or not self.expected_stderr
        ):
            status = TestStatus.ok
        else:
            status = TestStatus.wrong_answer

        why = None

        if state.exit_code:
            status = TestStatus.runtime_error
            why = stderr

        if state.cpu_limit:
            status = TestStatus.time_limit
            why = "Time limit has occurred"
        elif state.memory_limit:
            status = TestStatus.memory_limit
            why = "Memory limit has occurred"

        duration = state.finished_at - state.started_at

        return TestResult(status=status, why=why, duration=duration.total_seconds())
