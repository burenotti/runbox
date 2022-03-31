from typing import Sequence

from .proto import Mark, TotalScoringStrategy, UnitScoringStrategy
from ..testing.proto import TestResult

__all__ = [
    'BaseScoringSystem'
]


class BaseScoringSystem:

    def __init__(self):
        self._unit_scoring_strategy: UnitScoringStrategy | None = None
        self._total_scoring_strategy: TotalScoringStrategy | None = None

    async def estimate(self, test_results: Sequence[TestResult]) -> Mark:
        marks = tuple(map(self._unit_scoring_strategy, test_results))
        return self._total_scoring_strategy(test_results, marks)

    def set_unit_scoring_strategy(self, strategy: UnitScoringStrategy):
        self._unit_scoring_strategy = strategy

    def set_total_scoring_strategy(self, strategy: TotalScoringStrategy):
        self._total_scoring_strategy = strategy
