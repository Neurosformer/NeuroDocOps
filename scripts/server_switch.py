#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    if args.command == "on":
        command = [python_bin(repo_root), "scripts/orchestrate_stack.py"]
        if args.no_build:
            command.append("--no-build")
        if args.skip_smoke:
            command.append("--skip-smoke")
        return run(repo_root, command)
    if args.command == "off":
        return run(repo_root, compose_cmd("down"))
    if args.command == "status":
        return run(repo_root, compose_cmd("ps"))
    if args.command == "logs":
        return run(repo_root, compose_cmd("logs", "--follow"))
    raise AssertionError(f"Unhandled command: {args.command}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-command NeuroDocOps local server switch.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    on = subparsers.add_parser("on", help="Build/start the full local stack and run smoke checks.")
    on.add_argument("--no-build", action="store_true", help="Start existing images without rebuilding.")
    on.add_argument("--skip-smoke", action="store_true", help="Start services without running the workflow smoke test.")
    subparsers.add_parser("off", help="Stop the full local stack.")
    subparsers.add_parser("status", help="Show service status.")
    subparsers.add_parser("logs", help="Follow service logs.")
    return parser.parse_args()


def python_bin(repo_root: Path) -> str:
    venv_python = repo_root / ".venv/bin/python"
    return str(venv_python) if venv_python.exists() else sys.executable


def compose_cmd(*extra: str) -> list[str]:
    return ["docker", "compose", "-f", "infra/docker-compose.yml", "-p", "neurodocops", *extra]


def run(cwd: Path, command: list[str]) -> int:
    print(f"$ {' '.join(command)}")
    return subprocess.run(command, cwd=cwd, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
