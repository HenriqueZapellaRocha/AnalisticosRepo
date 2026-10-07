from __future__ import annotations

import random
import unittest

from jar_reference import ROOT, assert_model_matches_jar


def queue(
    servers: int,
    min_service: float,
    max_service: float,
    *,
    capacity: int | None = None,
    arrivals: tuple[float, float] | None = None,
) -> dict[str, int | float]:
    result: dict[str, int | float] = {
        "servers": servers,
        "minService": min_service,
        "maxService": max_service,
    }
    if capacity is not None:
        result["capacity"] = capacity
    if arrivals is not None:
        result["minArrival"], result["maxArrival"] = arrivals
    return result


def seeded_model(
    queues: dict[str, dict[str, int | float]],
    arrivals: dict[str, float],
    network: list[dict[str, str | float]],
    *,
    seeds: list[int] | None = None,
    count: int = 100_000,
) -> dict[str, object]:
    return {
        "arrivals": arrivals,
        "queues": queues,
        "network": network,
        "rndnumbersPerSeed": count,
        "seeds": seeds or [1],
    }


class JarDifferentialTest(unittest.TestCase):
    """Todos os cenários desta classe são comparados ao .jar em tempo real."""

    def test_assignment_model_matches_jar(self) -> None:
        assert_model_matches_jar(
            self,
            model_path=ROOT / "models" / "atividade.yml",
        )

    def test_module_3_example_with_five_seeds_matches_jar(self) -> None:
        assert_model_matches_jar(
            self,
            model_path=ROOT / "modulo3" / "model.yml",
        )

    def test_simma_repository_random_stream_matches_jar(self) -> None:
        # O repositório SimMA usa outro LCG. Fornecemos seus 100.000 valores
        # explicitamente aos dois simuladores para isolar e validar o motor.
        state = 42
        random_numbers = []
        for _ in range(100_000):
            state = (1_664_525 * state + 1_013_904_223) % (2**32)
            random_numbers.append(state / (2**32))

        model = {
            "arrivals": {"Q1": 2.5},
            "queues": {
                "Q1": queue(2, 4.0, 5.0, capacity=3, arrivals=(1.0, 5.0)),
                "Q2": queue(1, 1.0, 3.0, capacity=5),
            },
            "network": [
                {"source": "Q1", "target": "Q2", "probability": 1.0}
            ],
            "rndnumbers": random_numbers,
        }
        assert_model_matches_jar(self, model=model)

    def test_curated_topologies_match_jar(self) -> None:
        cases = {
            "single_infinite": seeded_model(
                {"Q1": queue(1, 2.0, 4.0, arrivals=(1.0, 3.0))},
                {"Q1": 1.5},
                [],
            ),
            "single_finite_many_servers": seeded_model(
                {"Q1": queue(3, 3.0, 8.0, capacity=4, arrivals=(0.5, 2.0))},
                {"Q1": 0.25},
                [],
            ),
            "tandem": seeded_model(
                {
                    "Q1": queue(2, 4.0, 5.0, capacity=3, arrivals=(1.0, 5.0)),
                    "Q2": queue(1, 1.0, 3.0, capacity=5),
                },
                {"Q1": 2.5},
                [{"source": "Q1", "target": "Q2", "probability": 1.0}],
                seeds=[42],
            ),
            "residual_exit_probability": seeded_model(
                {
                    "Q1": queue(2, 1.0, 2.0, capacity=5, arrivals=(2.0, 4.0)),
                    "Q2": queue(1, 3.0, 7.0, capacity=4),
                },
                {"Q1": 2.0},
                [{"source": "Q1", "target": "Q2", "probability": 0.37}],
            ),
            "self_loop": seeded_model(
                {"Q1": queue(2, 0.5, 2.5, capacity=7, arrivals=(2.0, 6.0))},
                {"Q1": 0.75},
                [{"source": "Q1", "target": "Q1", "probability": 0.72}],
            ),
            "three_queue_cycle": seeded_model(
                {
                    "A": queue(1, 1.0, 3.0, capacity=4, arrivals=(1.0, 4.0)),
                    "B": queue(3, 2.0, 8.0, capacity=8),
                    "C": queue(2, 3.0, 5.0),
                },
                {"A": 1.25},
                [
                    {"source": "A", "target": "B", "probability": 0.65},
                    {"source": "A", "target": "C", "probability": 0.20},
                    {"source": "B", "target": "C", "probability": 0.55},
                    {"source": "B", "target": "A", "probability": 0.15},
                    {"source": "C", "target": "A", "probability": 0.40},
                ],
            ),
            "multiple_external_arrivals": seeded_model(
                {
                    "IN1": queue(1, 1.0, 2.0, capacity=3, arrivals=(1.0, 3.0)),
                    "IN2": queue(2, 2.0, 4.0, capacity=5, arrivals=(2.0, 6.0)),
                    "OUT": queue(3, 1.0, 5.0, capacity=9),
                },
                {"IN1": 0.5, "IN2": 1.125},
                [
                    {"source": "IN1", "target": "OUT", "probability": 1.0},
                    {"source": "IN2", "target": "OUT", "probability": 0.80},
                ],
            ),
            "unsorted_route_probabilities": seeded_model(
                {
                    "Q1": queue(1, 1.0, 2.0, capacity=5, arrivals=(2.0, 4.0)),
                    "Q2": queue(2, 2.0, 5.0, capacity=5),
                    "Q3": queue(2, 2.0, 5.0, capacity=5),
                    "Q4": queue(2, 2.0, 5.0, capacity=5),
                },
                {"Q1": 2.0},
                [
                    {"source": "Q1", "target": "Q2", "probability": 0.60},
                    {"source": "Q1", "target": "Q3", "probability": 0.10},
                    {"source": "Q1", "target": "Q4", "probability": 0.25},
                ],
            ),
            "multiple_seeds": seeded_model(
                {
                    "Q1": queue(2, 1.0, 4.0, capacity=6, arrivals=(1.0, 3.0)),
                    "Q2": queue(1, 2.0, 7.0, capacity=4),
                },
                {"Q1": 1.0},
                [{"source": "Q1", "target": "Q2", "probability": 0.75}],
                seeds=[1, 7, 42, 999],
                count=50_000,
            ),
        }

        for name, model in cases.items():
            with self.subTest(name=name):
                assert_model_matches_jar(self, model=model)

    def test_random_number_exhaustion_at_event_boundaries_matches_jar(self) -> None:
        # Listas curtas forçam o término em pontos diferentes de chegada,
        # atendimento, passagem e agendamento da próxima chegada.
        base_numbers = [
            0.2176,
            0.0103,
            0.1109,
            0.3456,
            0.9910,
            0.2323,
            0.9211,
            0.0322,
            0.1211,
            0.5131,
            0.7208,
            0.9172,
            0.9922,
            0.8324,
            0.5011,
            0.2931,
        ]
        for length in range(1, len(base_numbers) + 1):
            model = {
                "arrivals": {"Q1": 2.0},
                "queues": {
                    "Q1": queue(1, 1.0, 2.0, capacity=3, arrivals=(2.0, 4.0)),
                    "Q2": queue(2, 3.0, 6.0, capacity=4),
                    "Q3": queue(1, 2.0, 7.0, capacity=2),
                },
                "network": [
                    {"source": "Q1", "target": "Q2", "probability": 0.25},
                    {"source": "Q1", "target": "Q3", "probability": 0.55},
                    {"source": "Q2", "target": "Q1", "probability": 0.40},
                ],
                "rndnumbers": base_numbers[:length],
            }
            with self.subTest(random_numbers=length):
                assert_model_matches_jar(self, model=model)

    def test_deterministically_generated_networks_match_jar(self) -> None:
        generator = random.Random(20_261_007)
        for case_index in range(24):
            queue_count = 1 + case_index % 6
            queues: dict[str, dict[str, int | float]] = {}
            for index in range(queue_count):
                servers = 1 + (case_index + index) % 4
                finite = (case_index + index) % 3 != 0
                capacity = servers + generator.randint(0, 5) if finite else None
                minimum = round(generator.uniform(0.25, 6.0), 3)
                maximum = round(minimum + generator.uniform(0.1, 9.0), 3)
                arrival_range = None
                if index == 0:
                    arrival_minimum = round(generator.uniform(0.2, 4.0), 3)
                    arrival_range = (
                        arrival_minimum,
                        round(arrival_minimum + generator.uniform(0.2, 5.0), 3),
                    )
                queues[f"Q{index}"] = queue(
                    servers,
                    minimum,
                    maximum,
                    capacity=capacity,
                    arrivals=arrival_range,
                )

            network: list[dict[str, str | float]] = []
            if queue_count > 1:
                for source_index in range(queue_count):
                    first_probability = [0.15, 0.30, 0.55, 0.80][
                        (case_index + source_index) % 4
                    ]
                    network.append(
                        {
                            "source": f"Q{source_index}",
                            "target": f"Q{(source_index + 1) % queue_count}",
                            "probability": first_probability,
                        }
                    )
                    if queue_count >= 3 and first_probability <= 0.55:
                        network.append(
                            {
                                "source": f"Q{source_index}",
                                "target": f"Q{(source_index + 2) % queue_count}",
                                "probability": 0.15,
                            }
                        )

            model = seeded_model(
                queues,
                {"Q0": round(generator.uniform(0.0, 3.0), 3)},
                network,
                seeds=[case_index + 1, case_index + 10_001],
                count=25_000,
            )
            with self.subTest(case=case_index, queues=queue_count):
                assert_model_matches_jar(self, model=model)


if __name__ == "__main__":
    unittest.main()
