import asyncio

from runbox.shortucts import execute
from runbox.models import (
    DockerProfile, File
)

profile = DockerProfile(
    image='python-sandbox:latest',
    workdir='/sandbox',
    cmd_template=["python", ...],
    user='sandbox'
)

file = File(
    name='main.py',
    content='name = input("What is your name?\\n")\n'
            'print(f"Hello, {name}")'
)


async def main():
    logs = execute(profile, [file], stdin=b'Jack\n')

    async for log in logs:
        print(log)


asyncio.run(main())
