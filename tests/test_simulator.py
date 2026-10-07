from __future__ import annotations

import unittest
from pathlib import Path

from simulator import Simulator, load_config
from simulator.config import QueueConfig, RouteConfig, SimulationConfig
from simulator.random_source import LinearCongruentialGenerator


ROOT = Path(__file__).resolve().parents[1]


class RandomGeneratorTest(unittest.TestCase):
    def test_lcg_uses_the_same_formula_as_the_reference(self) -> None:
        generator = LinearCongruentialGenerator(limit=2, seed=1)
        expected_state = (
            generator.MULTIPLIER * 1 + generator.INCREMENT
        ) % generator.MODULUS
        self.assertEqual(generator.next(), expected_state / generator.MODULUS)
        self.assertEqual(generator.consumed, 1)


class ActivitySimulationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = Simulator(load_config(ROOT / "models" / "atividade.yml")).run()

    def test_consumes_exactly_100000_random_numbers(self) -> None:
        self.assertEqual(self.result.runs[0].random_numbers_consumed, 100_000)

    def test_state_times_form_a_probability_distribution(self) -> None:
        for queue in self.result.queues:
            with self.subTest(queue=queue.name):
                self.assertAlmostEqual(
                    sum(queue.state_times.values()),
                    self.result.total_time,
                    places=7,
                )

    def test_finite_queues_never_report_states_over_capacity(self) -> None:
        for queue in self.result.queues:
            if queue.capacity is not None:
                self.assertLessEqual(max(queue.state_times), queue.capacity)

    def test_result_matches_module_3_reference_simulator(self) -> None:
        queues = {queue.name: queue for queue in self.result.queues}
        self.assertAlmostEqual(self.result.total_time, 50_655.0309, places=4)
        self.assertEqual(queues["Q1"].losses, 0)
        self.assertEqual(queues["Q2"].losses, 4)
        self.assertEqual(queues["Q3"].losses, 11_676)
        self.assertAlmostEqual(queues["Q1"].state_times[0], 20_236.9491, places=4)
        self.assertAlmostEqual(queues["Q2"].state_times[5], 57.7348, places=4)
        self.assertAlmostEqual(queues["Q3"].state_times[10], 31_938.6922, places=4)


class SimMARepositoryCompatibilityTest(unittest.TestCase):
    def test_tandem_case_matches_published_results(self) -> None:
        # Sequência produzida pelo LCG publicado em pcbelloc/SimMA:
        # seed=42, a=1664525, c=1013904223 e m=2**32.
        state = 42
        random_numbers = []
        for _ in range(100_000):
            state = (1_664_525 * state + 1_013_904_223) % (2**32)
            random_numbers.append(state / (2**32))

        config = SimulationConfig(
            queues={
                "Q1": QueueConfig("Q1", 2, 3, 4.0, 5.0, 1.0, 5.0),
                "Q2": QueueConfig("Q2", 1, 5, 1.0, 3.0),
            },
            arrivals={"Q1": 2.5},
            routes=(RouteConfig("Q1", "Q2", 1.0),),
            random_numbers=tuple(random_numbers),
            seeds=(),
            random_numbers_per_seed=100_000,
        )
        result = Simulator(config).run()
        queues = {queue.name: queue for queue in result.queues}

        self.assertAlmostEqual(result.total_time, 100_895.55724, places=5)
        self.assertEqual(queues["Q1"].losses, 361)
        self.assertEqual(queues["Q2"].losses, 0)
        expected_q1 = {
            0: 1_144.20127,
            1: 50_053.89494,
            2: 43_527.63780,
            3: 6_169.82323,
        }
        expected_q2 = {
            0: 34_292.14499,
            1: 60_360.78334,
            2: 6_228.94916,
            3: 13.67975,
            4: 0.0,
            5: 0.0,
        }
        for state, expected in expected_q1.items():
            self.assertAlmostEqual(queues["Q1"].state_times[state], expected, places=5)
        for state, expected in expected_q2.items():
            self.assertAlmostEqual(queues["Q2"].state_times[state], expected, places=5)


if __name__ == "__main__":
    unittest.main()
