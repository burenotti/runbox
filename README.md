# RunBox

**RunBox** is an asynchronous library written in Python for compiling, running and testing an
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

    # Workdir is a temporary volume, that provides you a way to share data between a couple of containers
    # Volume will be deleted upon exiting the context manager
    async with executor.workdir() as workdir:
        container = await executor.create_container(
            profile=profile,
            limits=limits,
            files=[file],
            workdir=workdir
        )

        # Context manager will automatically remove container on exit
        async with container as sandbox:
            await sandbox.run(stdin=b'John\n')
            # Wait until the container stops or is killed due to the timeout
            await sandbox.wait()
            logs = await sandbox.log(stdout=True)

            print(logs)

    await executor.close()


if __name__ == '__main__':
    asyncio.run(main())

```

### Testing and scoring solutions

This library is capable of testing a code it gets.
So lets test something!

For example, let's do something simple: FizzBuzz.  

The rules are as follows: if the number is divides by 3, we print `Fizz`, if it's divides by 5 — `Buzz`. 
And we print `FizzBuzz` if the number is divides by both.

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
protocols. You can implement them by yourself, but here we will
use a built-in implementations.


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

Firstly, we create a `DockerProfile`. This model contains
information about docker image that will be used.

Secondly, we add `Limits`:
- 3 seconds for execution
- 64 MB of RAM.

Thirdly, we add a `File` object, a piece of code that we will execute.

Now we are ready to begin.

```python
async def test_fizz_buzz():
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


# Runbox is an asynchronous library, so we need an async main function
async def main():
    
    results = await test_fizz_buzz()
    print(results, sep='\n')
    # Output will be as follows:
    # status=<TestStatus.ok: 'OK'> why=None
    # status=<TestStatus.ok: 'OK'> why=None
    # status=<TestStatus.ok: 'OK'> why=None
    # status=<TestStatus.ok: 'OK'> why=None
    # status=<TestStatus.runtime_error: 'RE'> why='Here the TypeError exception'
    
    
    # Don't forget to close `executor`.
    await executor.close()


if __name__ == '__main__':
    asyncio.run(main())
```
We also may need to rate (score) a solution.
For that RunBox provides `ScoringSystem` Protocol.
And a `BaseScoringSystem`, simple implementation.

`ScoringSystem` uses two strategies: `UnitScoringStrategy` and 
`TotalScoringStrategy`. This provides some flexibility in scoring.

Reimplementation of the `UnitScoringStrategy` allows you to change scoring
of a single test case. For example, you might want some tests to
weight more than others according to execution time or something else.

Reimplementation of the `TotalScoringStrategy` allows you to change 
scoring of the whole test suite. 
For example, changing this strategy you can fail the whole test suite if a single test fails
or set the minimum total score, that suite should gain. 

Let's score our FizzBuzz, using a built-in `BaseScoringSystem`. 

```python
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
