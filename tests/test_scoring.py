from typing import Sequence

import pytest

from runbox.scoring import *
from runbox.testing.proto import TestResult, TestStatus


@pytest.fixture
def ok_test_result() -> TestResult:
    return TestResult(status=TestStatus.ok)


@pytest.fixture
def rt_test_result() -> TestResult:
    return TestResult(status=TestStatus.runtime_error)


@pytest.fixture
def test_results() -> Sequence[TestResult]:
    return [
        TestResult(status=TestStatus.ok),
        TestResult(status=TestStatus.ok),
        TestResult(status=TestStatus.ok),
        TestResult(status=TestStatus.ok),
        TestResult(status=TestStatus.ok),
        TestResult(status=TestStatus.ok),
        TestResult(status=TestStatus.ok),
        TestResult(status=TestStatus.ok),
        TestResult(status=TestStatus.time_limit),
        TestResult(status=TestStatus.wrong_answer),
    ]


@pytest.fixture
def proportional_strategy(test_results) -> UnitScoringStrategy:
    return proportional_unit_scoring(len(test_results), 100, 0)


def test_prop_strategy(ok_test_result, rt_test_result):
    strategy = proportional_unit_scoring(20, 100, 0)
    assert strategy(ok_test_result) == 5.0
    assert strategy(rt_test_result) == 0.0


def test_total_strategy_no_threshold(test_results, proportional_strategy):
    strategy = total_scoring(0.0)
    marks = tuple(map(proportional_strategy, test_results))
    mark = strategy(test_results, marks)
    assert mark == 80


def test_total_strategy_threshold(test_results, proportional_strategy):
    strategy = total_scoring(0.0, threshold=90)
    marks = tuple(map(proportional_strategy, test_results))
    mark = strategy(test_results, marks)
    assert mark == 0.0


@pytest.mark.asyncio
async def test_base_scoring_system(test_results):
    scoring_system = BaseScoringSystem()
    unit_strategy = proportional_unit_scoring(len(test_results), 100, 0.0)
    total_strategy = total_scoring(0.0, 75)
    scoring_system.set_unit_scoring_strategy(unit_strategy)
    scoring_system.set_total_scoring_strategy(total_strategy)
    result = await scoring_system.estimate(test_results)
    assert result == 80
