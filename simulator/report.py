from __future__ import annotations

from .engine import QueueResult, SimulationResult


def _queue_description(queue: QueueResult) -> str:
    capacity = "" if queue.capacity is None else f"/{queue.capacity}"
    return f"G/G/{queue.servers}{capacity}"


def format_report(result: SimulationResult) -> str:
    lines = [
        "=" * 67,
        "SIMULADOR DE REDE DE FILAS — RELATÓRIO",
        "=" * 67,
    ]
    for run in result.runs:
        source = "lista fornecida" if run.seed is None else f"semente {run.seed}"
        lines.append(
            f"Simulação {run.number} ({source}): "
            f"tempo={run.simulation_time:.4f}, "
            f"aleatórios={run.random_numbers_consumed}"
        )

    total_time = result.total_time
    for queue in result.queues:
        lines.extend(
            [
                "",
                "-" * 67,
                f"Fila {queue.name} ({_queue_description(queue)})",
            ]
        )
        if queue.min_arrival is not None:
            lines.append(
                f"Chegadas: U({queue.min_arrival:.1f}, {queue.max_arrival:.1f})"
            )
        lines.extend(
            [
                f"Atendimento: U({queue.min_service:.1f}, {queue.max_service:.1f})",
                f"{'Estado':>8} {'Tempo acumulado':>22} {'Probabilidade':>20}",
            ]
        )
        for state, elapsed in sorted(queue.state_times.items()):
            probability = elapsed / total_time if total_time else 0.0
            lines.append(f"{state:>8} {elapsed:>22.4f} {probability:>19.4%}")
        lines.append(f"Perdas de clientes: {queue.losses}")

    lines.extend(
        [
            "",
            "=" * 67,
            f"Tempo global total: {result.total_time:.4f}",
            f"Tempo global médio: {result.average_time:.4f}",
            "=" * 67,
        ]
    )
    return "\n".join(lines)
