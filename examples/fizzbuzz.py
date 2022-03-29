import asyncio
from datetime import timedelta

import runbox
from runbox import DockerSandbox
from runbox.models import (
    DockerProfile, Limits, File
)

profile = DockerProfile(
    image='python-sandbox:latest',
    workdir_mount='/sandbox',
    exec='python',
    user='sandbox'
)

limits = Limits(
    time=timedelta(seconds=3),
    memory_mb=64,
)

content = """
# FizzBuzz

n = int(input())

if n % 3 == 0 and n % 5 == 0:
    print("FizzBuzz")
elif n % 3 == 0:
    print("Fizz")
elif n % 5 == 0:
    print("Buzz")
else:
    print(n)
"""

file = File(name='main.py', content=content)


async def test_fizz_buzz(sandbox: DockerSandbox, number: int, expected_result: str):
    reader = await sandbox.run(stdin=f'{number}\n'.encode('utf-8'))
    await sandbox.wait()
    result = await reader.read_out()
    assert result.data.decode('utf-8') == expected_result


async def main():
    executor = runbox.DockerExecutor()

    async with executor.workdir() as workdir:
        container = await executor.create_container(
            profile=profile,
            limits=limits,
            files=[file],
            workdir=workdir
        )

        async with container as sandbox:
            await test_fizz_buzz(sandbox, 25, 'Buzz\n')
            await test_fizz_buzz(sandbox, 9, 'Fizz\n')
            await test_fizz_buzz(sandbox, 15, 'FizzBuzz\n')
            await test_fizz_buzz(sandbox, 13, '13\n')

    await executor.close()


if __name__ == '__main__':
    asyncio.run(main())
