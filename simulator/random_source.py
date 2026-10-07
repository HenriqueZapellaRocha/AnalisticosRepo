from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence


class RandomNumbersExhausted(RuntimeError):
    """Sinaliza que a quantidade configurada de aleatórios foi consumida."""


class RandomSource(ABC):
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.consumed = 0

    @property
    def has_next(self) -> bool:
        return self.consumed < self.limit

    def next(self) -> float:
        if not self.has_next:
            raise RandomNumbersExhausted("Os números pseudoaleatórios terminaram.")
        value = self._next_value()
        self.consumed += 1
        return value

    def uniform(self, minimum: float, maximum: float) -> float:
        return minimum + (maximum - minimum) * self.next()

    @abstractmethod
    def _next_value(self) -> float:
        raise NotImplementedError


class ListRandomSource(RandomSource):
    def __init__(self, values: Sequence[float]) -> None:
        self._values = tuple(values)
        super().__init__(len(self._values))

    def _next_value(self) -> float:
        return self._values[self.consumed]


class LinearCongruentialGenerator(RandomSource):
    """Mesmo gerador congruente linear utilizado pelo simulador do módulo 3."""

    MULTIPLIER = 25_214_903_917
    INCREMENT = 11
    MODULUS = 2**48

    def __init__(self, limit: int, seed: int = 1) -> None:
        super().__init__(limit)
        self._state = seed

    def _next_value(self) -> float:
        self._state = (
            self.MULTIPLIER * self._state + self.INCREMENT
        ) % self.MODULUS
        return self._state / self.MODULUS
