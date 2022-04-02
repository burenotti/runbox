# RunBox

**RunBox** is an asynchronous library created for compiling and running
untrusted code in a safe docker environment.


### Simple Example
```python
import asyncio
from datetime import timedelta

import runbox
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

file = File(
    name='main.py',
    content='name = input("What is your name?\\n")\n'
            'print(f"Hello, {name}")'
)


async def main():
    executor = runbox.DockerExecutor()

    # Workdir is a temporary volume, that provides you 
    # a way to share date between a couple of containers.
    # Volume will be deleted on exiting context manager
    async with executor.workdir() as workdir:
        container = await executor.create_container(
            profile=profile,
            limits=limits,
            files=[file],
            workdir=workdir
        )

        # Context manager will remove container on exiting
        async with container as sandbox:
            await sandbox.run(stdin=b'John\n')
            # Wait the container stops or be killed after timeout expires
            await sandbox.wait()
            logs = await sandbox.log(stdout=True)

            print(logs)

    await executor.close()


if __name__ == '__main__':
    asyncio.run(main())

```

### Testing and scoring solutions

This library was created for testing untrusted code.
So lets test something.

For example, we will take something easy. Let it be FizzBuzz.
If number divides by 3, we print `Fizz`, if by 5, `Buzz`
and `FizzBuzz` if number divides by both.

So, here is the code, that solves that task.
```python
n = int(input())

if n % 3 == 0 and n % 5 == 0:
    print("FizzBuzz")
elif n % 3 == 0:
    print("Fizz")
elif n % 5 == 0:
    print("Buzz")
else:
    print(n)
```

For testing purposes RunBox provides `TestCase` and `TestSuite`
protocols, those you can implement by yourselves, but now we will
use built-in implementations.


```python
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

```

First, we create a `DockerProfile`. This model contains
information about docker image, that we will use.

Second, we add a `Limits`:
- 3 seconds for execution
- 64 MB of RAM.

Third, a File object, a piece of code, that we execute.

Now we are ready to begin.

```python
async def test_fizz_buzz():
    # Executor is a class, that manages containers creation.
    executor = runbox.DockerExecutor()
    
    # TestSuites allows automatically run tests on given executor 
    # So it needs a profile, limits and files to run.
    test_suite = BaseTestSuite(profile, limits, [file])
    
    # Then we add a test cases in test suite.
    # IOTestCase simply run code with given stdin
    # and checks that stdout is exactly as expected.
    test_suite.add_tests(
        IOTestCase(b'15\n', b'FizzBuzz\n'),
        IOTestCase(b'25\n', b'Buzz\n'),
        IOTestCase(b'24\n', b'Fizz\n'),
        IOTestCase(b'19\n', b'19\n'),
        IOTestCase(b'12.3\n', b'')  # This case should always fail
    )
    
    # And now we execute test suite with docker executor.
    # results variable will contain a list of a TestResults
    results = await test_suite.exec(executor)
    return results


# Runbox is an asynchronous library, so we need an async main
async def main():
    
    results = await test_fizz_buzz()
    print(results, sep='\n')
    # Output will be like this:
    # status=<TestStatus.ok: 'OK'> why=None
    # status=<TestStatus.ok: 'OK'> why=None
    # status=<TestStatus.ok: 'OK'> why=None
    # status=<TestStatus.ok: 'OK'> why=None
    # status=<TestStatus.runtime_error: 'RE'> why='Here the TypeError exception'
    
    
    # Don't forget to close executor.
    await executor.close()


if __name__ == '__main__':
    asyncio.run(main())
```
But also we may need to give a score to a solution.
For that RunBox provides `ScoringSystem` Protocol.
And a `BaseScoringSystem`, simple implementation.

`ScoringSystem` uses two strategies: `UnitScoringStrategy` and 
`TotalScoringStrategy`. This gives some flexibility in scoring.

Reimplementing of the **UnitScoringStrategy** allows you to change scoring
of a single test case. For example, you might want some tests
weight more than others according to execution time or anything else.

Reimplementing of the **TotalScoringStrategy** allows you to change 
scoring of the whole test suite. 
For example, changing this strategy you can fail whole test suite if any test fail
or set the minimum total score, that suite should gain. 

So, lets score our FizzBuzz, using built-in `BaseScoringSystem`. 

```python
async def score_fizz_buzz(results):
    scoring = BaseScoringSystem()

    
    # proportional_unit_scoring is a UnitScoringStrategy
    # implementation. It splits the max_score between
    # test_count test cases.
    # For example, if you have 20 tests and 
    # the max_score is 100, each test can gain 5 points.
    # Default is a mark that strategy returns, if test is not ok. 
    us = proportional_unit_scoring(
        tests_count=len(results),
        max_score=100,
        default=0,
    )
    # total_scoring strategy is a TotalScoringStrategy
    # implementation. It just sums the scores of each
    # test case and check, that sum is above the given
    # threshold.
    ts = total_scoring(default=0, threshold=0)
    
    
    scoring.set_total_scoring_strategy(ts)
    scoring.set_unit_scoring_strategy(us)

    # And estimating result. It will return
    # the result of a TotalScoringStrategy
    score = await scoring.estimate(results)
    return score


async def main():
    
    results = await test_fizz_buzz()
    
    print(results, sep='\n')
    
    # And also change our main.
    score = score_fizz_buzz(results)

    # That solution will gain 80/100. 
    print(f"This solution scored {score}/100 points")
    
    await executor.close()
    

if __name__ == '__main__':
    asyncio.run(main())
```