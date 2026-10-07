from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .config import QueueConfig, RouteConfig, SimulationConfig
from .random_source import (
    LinearCongruentialGenerator,
    ListRandomSource,
    RandomNumbersExhausted,
    RandomSource,
)


class EventType(Enum):
    EXTERNAL_ARRIVAL = "chegada"
    SERVICE_COMPLETION = "saida"


@dataclass(order=True, slots=True)
class Event:
    time: float
    sequence: int
    event_type: EventType = field(compare=False)
    source: str = field(compare=False)
    destination: str | None = field(default=None, compare=False)


@dataclass(slots=True)
class QueueState:
    config: QueueConfig
    routes: list[RouteConfig] = field(default_factory=list)
    population: int = 0
    maximum_population: int = 0
    losses: int = 0
    state_times: dict[int, float] = field(
        default_factory=lambda: defaultdict(float)
    )

    def reset_population(self) -> None:
        self.population = 0


@dataclass(frozen=True, slots=True)
class RunResult:
    number: int
    seed: int | None
    simulation_time: float
    random_numbers_consumed: int


@dataclass(frozen=True, slots=True)
class QueueResult:
    name: str
    servers: int
    capacity: int | None
    min_arrival: float | None
    max_arrival: float | None
    min_service: float
    max_service: float
    state_times: dict[int, float]
    losses: int


@dataclass(frozen=True, slots=True)
class SimulationResult:
    runs: tuple[RunResult, ...]
    queues: tuple[QueueResult, ...]

    @property
    def total_time(self) -> float:
        return sum(run.simulation_time for run in self.runs)

    @property
    def average_time(self) -> float:
        return self.total_time / len(self.runs) if self.runs else 0.0

    def as_dict(self) -> dict[str, Any]:
        total_time = self.total_time
        return {
            "runs": [
                {
                    "number": run.number,
                    "seed": run.seed,
                    "simulation_time": run.simulation_time,
                    "random_numbers_consumed": run.random_numbers_consumed,
                }
                for run in self.runs
            ],
            "total_time": total_time,
            "average_time": self.average_time,
            "queues": [
                {
                    "name": queue.name,
                    "servers": queue.servers,
                    "capacity": queue.capacity,
                    "losses": queue.losses,
                    "states": [
                        {
                            "state": state,
                            "time": elapsed,
                            "probability": elapsed / total_time if total_time else 0.0,
                        }
                        for state, elapsed in sorted(queue.state_times.items())
                    ],
                }
                for queue in self.queues
            ],
        }


class Simulator:
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self.queues = {
            name: QueueState(queue_config)
            for name, queue_config in config.queues.items()
        }
        for route in config.routes:
            self.queues[route.source].routes.append(route)
        # O .jar ordena as alternativas pela probabilidade antes do sorteio.
        for queue in self.queues.values():
            queue.routes.sort(key=lambda route: route.probability)

        self._events: list[Event] = []
        self._sequence = 0
        self._clock = 0.0
        self._random: RandomSource | None = None

    def run(self) -> SimulationResult:
        # Permite reutilizar a mesma instância sem carregar estatísticas antigas.
        for queue in self.queues.values():
            queue.population = 0
            queue.maximum_population = 0
            queue.losses = 0
            queue.state_times.clear()

        run_results: list[RunResult] = []
        if self.config.seeds:
            sources = [
                (
                    seed,
                    LinearCongruentialGenerator(
                        self.config.random_numbers_per_seed, seed
                    ),
                )
                for seed in self.config.seeds
            ]
        else:
            sources = [(None, ListRandomSource(self.config.random_numbers))]

        for number, (seed, random_source) in enumerate(sources, start=1):
            self._prepare_run(random_source)
            self._execute()
            run_results.append(
                RunResult(
                    number=number,
                    seed=seed,
                    simulation_time=self._clock,
                    random_numbers_consumed=random_source.consumed,
                )
            )

        queue_results = tuple(
            QueueResult(
                name=name,
                servers=state.config.servers,
                capacity=state.config.capacity,
                min_arrival=state.config.min_arrival,
                max_arrival=state.config.max_arrival,
                min_service=state.config.min_service,
                max_service=state.config.max_service,
                state_times=self._reported_state_times(state),
                losses=state.losses,
            )
            for name, state in self.queues.items()
        )
        return SimulationResult(tuple(run_results), queue_results)

    def _prepare_run(self, random_source: RandomSource) -> None:
        self._events = []
        self._sequence = 0
        self._clock = 0.0
        self._random = random_source
        for queue in self.queues.values():
            queue.reset_population()
        for queue_name, initial_time in self.config.arrivals.items():
            self._schedule(
                initial_time,
                EventType.EXTERNAL_ARRIVAL,
                source=queue_name,
            )

    def _execute(self) -> None:
        assert self._random is not None
        while self._random.has_next:
            if not self._events:
                raise RuntimeError("A agenda ficou vazia antes do fim da simulação.")
            event = heapq.heappop(self._events)
            try:
                self._process(event)
            except RandomNumbersExhausted:
                # Compatibilidade com a referência: o evento pode ter sido
                # parcialmente tratado quando o último aleatório foi usado.
                break

    def _process(self, event: Event) -> None:
        self._advance_clock(event.time)
        if event.event_type is EventType.EXTERNAL_ARRIVAL:
            self._arrival(event.source, external=True)
            return

        source = self.queues[event.source]
        if source.population <= 0:
            raise RuntimeError(f"Saída impossível na fila vazia '{event.source}'.")
        source.population -= 1

        # Se todos os servidores continuarem ocupados, o próximo cliente da
        # espera inicia atendimento imediatamente.
        if source.population >= source.config.servers:
            self._start_service(source)

        if event.destination is not None:
            self._arrival(event.destination, external=False)

    def _advance_clock(self, new_time: float) -> None:
        if new_time < self._clock:
            raise RuntimeError("A agenda produziu um evento no passado.")
        elapsed = new_time - self._clock
        for queue in self.queues.values():
            queue.state_times[queue.population] += elapsed
        self._clock = new_time

    def _arrival(self, queue_name: str, *, external: bool) -> None:
        queue = self.queues[queue_name]
        capacity = queue.config.capacity
        if capacity is not None and queue.population >= capacity:
            queue.losses += 1
        else:
            queue.population += 1
            queue.maximum_population = max(
                queue.maximum_population, queue.population
            )
            if queue.population <= queue.config.servers:
                self._start_service(queue)

        if external:
            assert queue.config.min_arrival is not None
            assert queue.config.max_arrival is not None
            assert self._random is not None
            interval = self._random.uniform(
                queue.config.min_arrival, queue.config.max_arrival
            )
            self._schedule(
                self._clock + interval,
                EventType.EXTERNAL_ARRIVAL,
                source=queue_name,
            )

    def _start_service(self, queue: QueueState) -> None:
        assert self._random is not None
        destination = self._choose_destination(queue)
        duration = self._random.uniform(
            queue.config.min_service, queue.config.max_service
        )
        self._schedule(
            self._clock + duration,
            EventType.SERVICE_COMPLETION,
            source=queue.config.name,
            destination=destination,
        )

    def _choose_destination(self, queue: QueueState) -> str | None:
        if not queue.routes:
            return None
        if len(queue.routes) == 1 and queue.routes[0].probability >= 1:
            return queue.routes[0].target

        assert self._random is not None
        probability = self._random.next()
        for route in queue.routes:
            if probability <= route.probability:
                return route.target
            probability -= route.probability
        return None

    def _schedule(
        self,
        time: float,
        event_type: EventType,
        *,
        source: str,
        destination: str | None = None,
    ) -> None:
        self._sequence += 1
        heapq.heappush(
            self._events,
            Event(time, self._sequence, event_type, source, destination),
        )

    @staticmethod
    def _reported_state_times(queue: QueueState) -> dict[int, float]:
        if queue.config.capacity is not None:
            maximum = queue.config.capacity
        else:
            maximum = queue.maximum_population
        return {
            state: queue.state_times.get(state, 0.0)
            for state in range(maximum + 1)
        }
