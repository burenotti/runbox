from __future__ import annotations

from typing import Protocol, Sequence

from runbox.testing.proto import TestResult

__all__ = [
    'Mark', 'ScoringSystem',
    'UnitScoringStrategy',
    'TotalScoringStrategy',
]


class Mark(Protocol):

    def __str__(self) -> str:
        ...

    def __eq__(self, other) -> bool:
        ...

    def __ne__(self, other) -> bool:
        ...

    def __le__(self, other) -> bool:
        ...

    def __lt__(self, other) -> bool:
        ...

    def __ge__(self, other) -> bool:
        ...

    def __gt__(self, other) -> bool:
        ...

    def __add__(self, other) -> Mark:
        ...


class UnitScoringStrategy(Protocol):

    def __call__(self, test_result: TestResult) -> Mark:
        ...


class TotalScoringStrategy(Protocol):

    def __call__(
        self,
        test_results: Sequence[TestResult],
        marks: Sequence[Mark]
    ) -> Mark:
        ...


class ScoringSystem(Protocol):

    async def estimate(self, test_results: Sequence[TestResult]) -> Mark:
        ...

    def set_unit_scoring_strategy(self, strategy: UnitScoringStrategy):
        ...

    def set_total_scoring_strategy(self, strategy: TotalScoringStrategy):
        ...
