from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


EPSILON = 1e-12


class ConfigurationError(ValueError):
    """Indica que o modelo YAML não representa uma simulação válida."""


class ParametersLoader(yaml.SafeLoader):
    """SafeLoader que reconhece a tag usada pelo simulador do módulo 3."""


def _parameters_constructor(
    loader: ParametersLoader, node: yaml.nodes.MappingNode
) -> dict[str, Any]:
    return loader.construct_mapping(node, deep=True)


ParametersLoader.add_constructor("!PARAMETERS", _parameters_constructor)


@dataclass(frozen=True, slots=True)
class QueueConfig:
    name: str
    servers: int
    capacity: int | None
    min_service: float
    max_service: float
    min_arrival: float | None = None
    max_arrival: float | None = None


@dataclass(frozen=True, slots=True)
class RouteConfig:
    source: str
    target: str
    probability: float


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    queues: dict[str, QueueConfig]
    arrivals: dict[str, float]
    routes: tuple[RouteConfig, ...]
    random_numbers: tuple[float, ...]
    seeds: tuple[int, ...]
    random_numbers_per_seed: int


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"'{field}' deve ser um mapa YAML.")
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"'{field}' deve ser numérico.")
    return float(value)


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"'{field}' deve ser um número inteiro.")
    return value


def load_config(path: str | Path) -> SimulationConfig:
    model_path = Path(path)
    try:
        with model_path.open(encoding="utf-8") as model_file:
            raw = yaml.load(model_file, Loader=ParametersLoader)
    except OSError as error:
        raise ConfigurationError(f"Não foi possível abrir '{model_path}': {error}") from error
    except yaml.YAMLError as error:
        raise ConfigurationError(f"YAML inválido em '{model_path}': {error}") from error

    root = _mapping(raw, "raiz")
    raw_queues = _mapping(root.get("queues"), "queues")
    if not raw_queues:
        raise ConfigurationError("O modelo deve possuir ao menos uma fila.")

    queues: dict[str, QueueConfig] = {}
    for raw_name, raw_queue in raw_queues.items():
        name = str(raw_name)
        data = _mapping(raw_queue, f"queues.{name}")
        servers = _integer(data.get("servers"), f"queues.{name}.servers")
        if servers < 1:
            raise ConfigurationError(f"A fila '{name}' deve ter pelo menos um servidor.")

        raw_capacity = data.get("capacity")
        capacity = None
        if raw_capacity is not None:
            capacity = _integer(raw_capacity, f"queues.{name}.capacity")
            if capacity < 1:
                raise ConfigurationError(f"A capacidade da fila '{name}' deve ser positiva.")

        min_service = _number(data.get("minService"), f"queues.{name}.minService")
        max_service = _number(data.get("maxService"), f"queues.{name}.maxService")
        if min_service < 0 or max_service < min_service:
            raise ConfigurationError(
                f"Intervalo de atendimento inválido na fila '{name}'."
            )

        min_arrival = data.get("minArrival")
        max_arrival = data.get("maxArrival")
        if (min_arrival is None) != (max_arrival is None):
            raise ConfigurationError(
                f"A fila '{name}' deve informar minArrival e maxArrival em conjunto."
            )
        if min_arrival is not None:
            min_arrival = _number(min_arrival, f"queues.{name}.minArrival")
            max_arrival = _number(max_arrival, f"queues.{name}.maxArrival")
            if min_arrival < 0 or max_arrival < min_arrival:
                raise ConfigurationError(
                    f"Intervalo entre chegadas inválido na fila '{name}'."
                )

        queues[name] = QueueConfig(
            name=name,
            servers=servers,
            capacity=capacity,
            min_service=min_service,
            max_service=max_service,
            min_arrival=min_arrival,
            max_arrival=max_arrival,
        )

    raw_arrivals = _mapping(root.get("arrivals", {}), "arrivals")
    if not raw_arrivals:
        raise ConfigurationError("O modelo deve possuir ao menos uma chegada externa.")
    arrivals: dict[str, float] = {}
    for raw_name, raw_time in raw_arrivals.items():
        name = str(raw_name)
        if name not in queues:
            raise ConfigurationError(f"Chegada externa referencia fila inexistente: '{name}'.")
        if queues[name].min_arrival is None:
            raise ConfigurationError(
                f"A fila de entrada '{name}' não possui intervalo entre chegadas."
            )
        initial_time = _number(raw_time, f"arrivals.{name}")
        if initial_time < 0:
            raise ConfigurationError(f"A primeira chegada em '{name}' não pode ser negativa.")
        arrivals[name] = initial_time

    raw_network = root.get("network", [])
    if not isinstance(raw_network, list):
        raise ConfigurationError("'network' deve ser uma lista YAML.")
    routes: list[RouteConfig] = []
    probability_sums = {name: 0.0 for name in queues}
    for index, raw_route in enumerate(raw_network):
        data = _mapping(raw_route, f"network[{index}]")
        source = str(data.get("source"))
        target = str(data.get("target"))
        if source not in queues:
            raise ConfigurationError(f"Rota referencia origem inexistente: '{source}'.")
        if target not in queues:
            raise ConfigurationError(f"Rota referencia destino inexistente: '{target}'.")
        probability = _number(data.get("probability"), f"network[{index}].probability")
        if probability < 0 or probability > 1:
            raise ConfigurationError(
                f"Probabilidade inválida na rota {source} -> {target}: {probability}."
            )
        probability_sums[source] += probability
        routes.append(RouteConfig(source, target, probability))

    for source, total in probability_sums.items():
        if total > 1 + EPSILON:
            raise ConfigurationError(
                f"As probabilidades das rotas de '{source}' somam {total:.12g}, acima de 1."
            )

    raw_numbers = root.get("rndnumbers", []) or []
    if not isinstance(raw_numbers, list):
        raise ConfigurationError("'rndnumbers' deve ser uma lista YAML.")
    random_numbers = tuple(
        _number(value, f"rndnumbers[{index}]")
        for index, value in enumerate(raw_numbers)
    )
    for value in random_numbers:
        if value < 0 or value > 1:
            raise ConfigurationError("Todos os números aleatórios devem estar entre 0 e 1.")

    raw_seeds = root.get("seeds", []) or []
    if not isinstance(raw_seeds, list):
        raise ConfigurationError("'seeds' deve ser uma lista YAML.")
    seeds = tuple(_integer(value, f"seeds[{index}]") for index, value in enumerate(raw_seeds))

    random_numbers_per_seed = _integer(
        root.get("rndnumbersPerSeed", 100_000), "rndnumbersPerSeed"
    )
    if random_numbers_per_seed < 1:
        raise ConfigurationError("'rndnumbersPerSeed' deve ser positivo.")
    if not seeds and not random_numbers:
        raise ConfigurationError("Informe 'seeds' ou uma lista 'rndnumbers'.")

    return SimulationConfig(
        queues=queues,
        arrivals=arrivals,
        routes=tuple(routes),
        random_numbers=random_numbers,
        seeds=seeds,
        random_numbers_per_seed=random_numbers_per_seed,
    )
