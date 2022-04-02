import asyncio
from datetime import timedelta

import runbox
from runbox.models import (
    DockerProfile, Limits, File
)
from runbox.scoring import (
    BaseScoringSystem, total_scoring,
    proportional_unit_scoring
)
from runbox.testing import BaseTestSuite, IOTestCase

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


async def main():
    executor = runbox.DockerExecutor()
    test_suite = BaseTestSuite(profile, limits, [file])
    test_suite.add_tests(
        IOTestCase(b'15\n', b'FizzBuzz\n'),
        IOTestCase(b'25\n', b'Buzz\n'),
        IOTestCase(b'24\n', b'Fizz\n'),
        IOTestCase(b'19\n', b'19\n'),
        IOTestCase(b'12.3\n', b'')  # This case should always fail
    )
    results = await test_suite.exec(executor)
    print("Test results:", *results, sep='\n')

    scoring = BaseScoringSystem()

    ts = total_scoring(default=0, threshold=0)
    us = proportional_unit_scoring(
        tests_count=len(results),
        max_score=100,
        default=0,
    )
    scoring.set_total_scoring_strategy(ts)
    scoring.set_unit_scoring_strategy(us)

    score = await scoring.estimate(results)
    print(f"This solution scored {score}/{100} points")

    await executor.close()


if __name__ == '__main__':
    asyncio.run(main())
