"""On-demand analysis CLI: ``python -m chiron_entrypoint <ticker> <strategy>`` (AC4, FR-11).

Deliberately a minimal ``argparse`` wrapper, not ``chiron_cli``'s interactive
Typer/Rich app — this is a distinct, scriptable surface (FR-11 excludes
reusing the existing interactive CLI).
"""

import argparse
import asyncio
import logging
import sys

from chiron_entrypoint.entrypoint import VALID_STRATEGIES, EntrypointRequestError, run_analysis


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m chiron_entrypoint",
        description="Request an on-demand analysis for a tracked stock and strategy.",
    )
    parser.add_argument("ticker", help="Tracked ticker, e.g. PETR4.SA")
    parser.add_argument("strategy", choices=VALID_STRATEGIES, help="Strategy: day or swing")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = _parse_args()
    try:
        output_path = asyncio.run(run_analysis(args.ticker, args.strategy))
    except EntrypointRequestError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(output_path)


if __name__ == "__main__":
    main()
