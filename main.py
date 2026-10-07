from __future__ import annotations

import argparse
import json
import sys

from simulator import ConfigurationError, Simulator, load_config
from simulator.report import format_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simula uma rede arbitrária de filas descrita em YAML."
    )
    parser.add_argument("model", help="caminho do arquivo de modelo .yml")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emite o resultado em JSON, em vez do relatório textual",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = Simulator(load_config(args.model)).run()
    except (ConfigurationError, RuntimeError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
