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


async def fizz_buzz_test():
    # `DockerExecutor` is a class, that manages container creation
    executor = runbox.DockerExecutor()

    # `TestSuites` allows us to automatically run tests on a given executor
    # It needs `profile`, `limits` and `file` to run
    test_suite = BaseTestSuite(profile, limits, [file])

    # Then we add test cases in test suite
    # `IOTestCase` simply runs the code with a given stdin and checks if the stdout matches
    test_suite.add_tests(
        IOTestCase(b'15\n', b'FizzBuzz\n'),
        IOTestCase(b'25\n', b'Buzz\n'),
        IOTestCase(b'24\n', b'Fizz\n'),
        IOTestCase(b'19\n', b'19\n'),
        IOTestCase(b'12.3\n', b'')  # This case should always fail
    )

    # And now we execute test suite with `executor`
    # `results` variable will contain a list of a TestResults
    results = await test_suite.exec(executor)

    return results


async def score_fizz_buzz(results):
    scoring = BaseScoringSystem()

    # `proportional_unit_scoring` is a `UnitScoringStrategy` implementation.
    # It splits the `max_score` between `test_count` test cases.
    # For example, if you have 20 tests and the `max_score` is 100, each test can gain 5 points.
    # `default` is a mark that strategy returns if a test is not ok.
    us = proportional_unit_scoring(
        tests_count=len(results),
        max_score=100,
        default=0,
    )
    # `total_scoring` strategy is a `TotalScoringStrategy` implementation.
    # It sums up the scores of each test case and checks if that sum is above the given threshold.
    ts = total_scoring(default=0, threshold=0)

    scoring.set_total_scoring_strategy(ts)
    scoring.set_unit_scoring_strategy(us)

    # Estimating results will return the result of a `TotalScoringStrategy`
    score = await scoring.estimate(results)
    return score


# Runbox is an asynchronous library, so we need an async main function
async def main():
    results = await fizz_buzz_test()
    score = await score_fizz_buzz(results)

    print("Test results:", *results, sep='\n')
    # Output will be as follows:
    # status=<TestStatus.ok: 'OK'> why=None
    # status=<TestStatus.ok: 'OK'> why=None
    # status=<TestStatus.ok: 'OK'> why=None
    # status=<TestStatus.ok: 'OK'> why=None
    # status=<TestStatus.runtime_error: 'RE'> why='Here the TypeError exception'

    print(f"This solution scored {score}/{100} points")


if __name__ == '__main__':
    asyncio.run(main())
