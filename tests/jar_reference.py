from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from simulator import Simulator, load_config


ROOT = Path(__file__).resolve().parents[1]
JAR_PATH = ROOT / "modulo3" / "simulator.jar"

QUEUE_PATTERN = re.compile(r"^Queue:\s+(\S+)")
STATE_PATTERN = re.compile(
    r"^\s+(\d+)\s+([0-9]+,[0-9]+)\s+([0-9]+,[0-9]+)%\s*$"
)
LOSS_PATTERN = re.compile(r"^Number of losses:\s+(\d+)")
TIME_PATTERN = re.compile(r"^Simulation average time:\s+([0-9]+,[0-9]+)")


def _decimal(value: str) -> float:
    return float(value.replace(",", "."))


@dataclass(frozen=True, slots=True)
class JarQueueResult:
    state_times: dict[int, float]
    probabilities_percent: dict[int, float]
    losses: int


@dataclass(frozen=True, slots=True)
class JarResult:
    average_time: float
    queues: dict[str, JarQueueResult]


def parse_jar_report(output: str) -> JarResult:
    state_times: dict[str, dict[int, float]] = {}
    probabilities: dict[str, dict[int, float]] = {}
    losses: dict[str, int] = {}
    current_queue: str | None = None
    average_time: float | None = None

    for line in output.splitlines():
        if match := QUEUE_PATTERN.match(line):
            current_queue = match.group(1)
            state_times[current_queue] = {}
            probabilities[current_queue] = {}
            continue
        if current_queue is not None and (match := STATE_PATTERN.match(line)):
            state = int(match.group(1))
            state_times[current_queue][state] = _decimal(match.group(2))
            probabilities[current_queue][state] = _decimal(match.group(3))
            continue
        if current_queue is not None and (match := LOSS_PATTERN.match(line)):
            losses[current_queue] = int(match.group(1))
            continue
        if match := TIME_PATTERN.match(line):
            average_time = _decimal(match.group(1))

    if average_time is None:
        raise AssertionError(f"Tempo global ausente na saída do .jar:\n{output}")
    if not state_times:
        raise AssertionError(f"Nenhuma fila encontrada na saída do .jar:\n{output}")
    missing_losses = set(state_times) - set(losses)
    if missing_losses:
        raise AssertionError(
            f"Perdas ausentes para {sorted(missing_losses)} na saída do .jar."
        )

    return JarResult(
        average_time=average_time,
        queues={
            name: JarQueueResult(
                state_times=times,
                probabilities_percent=probabilities[name],
                losses=losses[name],
            )
            for name, times in state_times.items()
        },
    )


def run_jar(model_path: Path) -> JarResult:
    if shutil.which("java") is None:
        raise AssertionError("Java não está instalado; comparação com o .jar é obrigatória.")
    if not JAR_PATH.is_file():
        raise AssertionError(f"Simulador de referência não encontrado: {JAR_PATH}")

    completed = subprocess.run(
        ["java", "-jar", str(JAR_PATH), "run", str(model_path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"O .jar terminou com código {completed.returncode}.\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return parse_jar_report(completed.stdout)


def write_model(path: Path, model: dict[str, Any]) -> None:
    yaml_text = yaml.safe_dump(
        model,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    path.write_text(f"!PARAMETERS\n{yaml_text}", encoding="utf-8")


def assert_model_matches_jar(
    testcase: unittest.TestCase,
    *,
    model: dict[str, Any] | None = None,
    model_path: Path | None = None,
) -> None:
    if (model is None) == (model_path is None):
        raise ValueError("Informe exatamente um entre model e model_path.")

    if model_path is not None:
        _assert_path_matches_jar(testcase, model_path)
        return

    with tempfile.TemporaryDirectory(prefix="simulador-diferencial-") as temp_dir:
        temporary_model = Path(temp_dir) / "model.yml"
        assert model is not None
        write_model(temporary_model, model)
        _assert_path_matches_jar(testcase, temporary_model)


def _assert_path_matches_jar(
    testcase: unittest.TestCase, model_path: Path
) -> None:
    reference = run_jar(model_path)
    actual = Simulator(load_config(model_path)).run()
    actual_queues = {queue.name: queue for queue in actual.queues}

    testcase.assertEqual(set(actual_queues), set(reference.queues))
    testcase.assertAlmostEqual(
        actual.average_time,
        reference.average_time,
        delta=0.000051,
        msg="Tempo global diverge do simulador de referência.",
    )

    for name, expected_queue in reference.queues.items():
        actual_queue = actual_queues[name]
        testcase.assertEqual(
            actual_queue.losses,
            expected_queue.losses,
            f"Número de perdas diverge na fila {name}.",
        )
        all_states = set(actual_queue.state_times) | set(expected_queue.state_times)
        for state in all_states:
            expected_time = expected_queue.state_times.get(state, 0.0)
            actual_time = actual_queue.state_times.get(state, 0.0)
            testcase.assertAlmostEqual(
                actual_time,
                expected_time,
                delta=0.000051,
                msg=f"Tempo diverge na fila {name}, estado {state}.",
            )

            expected_probability = expected_queue.probabilities_percent.get(state, 0.0)
            actual_probability = (
                100.0 * actual_time / actual.total_time
                if actual.total_time
                else 0.0
            )
            testcase.assertAlmostEqual(
                actual_probability,
                expected_probability,
                delta=0.0051,
                msg=f"Probabilidade diverge na fila {name}, estado {state}.",
            )
