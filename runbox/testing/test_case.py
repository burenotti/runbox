from .proto import TestResult, TestStatus
from ..proto import Sandbox


class IOTestCase:

    def __init__(
        self,
        stdin: bytes | None = None,
        expected_stout:  bytes | None = None,
        expected_stderr: bytes | None = None,
        encoding: str = 'utf-8',
    ):
        self.expected_stout = expected_stout or b''
        self.expected_stderr = expected_stderr or b''
        self.stdin = stdin
        self.encoding = encoding

    async def exec(self, sandbox: Sandbox) -> TestResult:
        stdout = b''
        stderr = b''
        reader = await sandbox.run(self.stdin)
        while message := await reader.read_out():
            if message.stream == 1:
                stdout += message.data
            elif message.stream == 2:
                stderr += message.data

        await sandbox.wait()

        state = await sandbox.state()

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

        return TestResult(status=status, why=why)
