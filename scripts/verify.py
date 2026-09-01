from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*arguments: str) -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        env=environment,
        check=True,
    )


def main() -> int:
    run("-m", "unittest", "discover", "-s", "tests", "-v")
    run(
        "-m",
        "execution_monitor",
        "verify",
        "--output",
        "evidence/latest-verification.json",
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        run(
            "-m",
            "execution_monitor",
            "paper",
            "--data",
            "data/btc-usd-2026-08-29.csv",
            "--db",
            str(temp / "paper.db"),
            "--venue-state",
            str(temp / "paper-venue.json"),
            "--output",
            "evidence/paper-soak.json",
            "--trade-every",
            "6",
        )
    print("All Trading Execution Monitor checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
