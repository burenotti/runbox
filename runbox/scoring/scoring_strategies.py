from typing import Sequence

from .proto import UnitScoringStrategy, TotalScoringStrategy, Mark
from ..testing.proto import TestResult, TestStatus

__all__ = [
    'proportional_unit_scoring',
    'total_scoring',
]


def proportional_unit_scoring(
    tests_count: int,
    max_score: int,
    default: Mark,
) -> UnitScoringStrategy:
    points_per_test = max_score / tests_count

    def strategy(result: TestResult) -> Mark:
        return points_per_test if result.status == TestStatus.ok else default

    return strategy


def total_scoring(
    default: Mark,
    threshold: Mark = None,
) -> TotalScoringStrategy:
    def strategy(_: Sequence[TestResult], marks: Sequence[Mark]) -> Mark:
        mark = sum(marks)
        if threshold is None or threshold <= mark:
            return mark
        else:
            return default

    return strategy
