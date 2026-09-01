from __future__ import annotations

import argparse
import json
from pathlib import Path

from .demo import DemoLoop
from .models import Mode
from .monitor import ExecutionMonitor
from .paper import run_paper_soak
from .scenarios import generate_verification_bundle
from .server import build_server
from .simulator import SimulatedVenue


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="execution-monitor",
        description="Run and verify the public-safe Trading Execution Monitor demonstration.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Run the read-only local dashboard.")
    serve.add_argument(
        "--host",
        choices=["127.0.0.1", "localhost", "0.0.0.0"],
        default="127.0.0.1",
        help="0.0.0.0 is accepted only inside the explicitly configured container boundary.",
    )
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--db", type=Path, default=Path("var/demo.db"))
    serve.add_argument("--venue-state", type=Path, default=Path("var/demo-venue.json"))
    serve.add_argument(
        "--mode",
        choices=[Mode.SIMULATION.value, Mode.REPLAY.value, Mode.PAPER.value, Mode.TESTNET.value],
        default=Mode.SIMULATION.value,
    )
    serve.add_argument("--no-demo-loop", action="store_true")
    serve.add_argument("--delay", type=float, default=1.5)

    verify = subparsers.add_parser("verify", help="Generate deterministic verification evidence.")
    verify.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/latest-verification.json"),
    )

    paper = subparsers.add_parser(
        "paper",
        help="Run the deterministic paper soak against frozen public candles.",
    )
    paper.add_argument("--data", type=Path, default=Path("data/btc-usd-2026-08-29.csv"))
    paper.add_argument("--db", type=Path, default=Path("var/paper.db"))
    paper.add_argument("--venue-state", type=Path, default=Path("var/paper-venue.json"))
    paper.add_argument("--output", type=Path, default=Path("evidence/paper-soak.json"))
    paper.add_argument("--trade-every", type=int, default=6)
    return parser


def run_server(args: argparse.Namespace) -> int:
    venue = SimulatedVenue(state_path=args.venue_state)
    monitor = ExecutionMonitor(args.db, venue, mode=Mode(args.mode))
    monitor.recover_from_venue()
    server = build_server(monitor, host=args.host, port=args.port)
    demo = None if args.no_demo_loop else DemoLoop(monitor, delay=args.delay)
    if demo:
        demo.start()

    print(f"Execution Monitor dashboard: http://{args.host}:{server.server_port}")
    print("Read-only local demonstration. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if demo:
            demo.stop()
        server.server_close()
        monitor.close()
    return 0


def run_verify(args: argparse.Namespace) -> int:
    bundle = generate_verification_bundle(args.output, mode=Mode.SIMULATION)
    print(json.dumps(bundle, indent=2, sort_keys=True))
    return 0 if bundle["overall_result"] == "passed" else 1


def run_paper(args: argparse.Namespace) -> int:
    result = run_paper_soak(
        args.data,
        database_path=args.db,
        venue_state_path=args.venue_state,
        output_path=args.output,
        trade_every=args.trade_every,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_result"] == "passed" else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        return run_server(args)
    if args.command == "verify":
        return run_verify(args)
    if args.command == "paper":
        return run_paper(args)
    raise AssertionError(f"Unhandled command: {args.command}")
