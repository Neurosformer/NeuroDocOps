#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    try:
        if args.all_checks or args.unit:
            run(repo_root, [".venv/bin/pytest", "-q"] if (repo_root / ".venv/bin/pytest").exists() else ["pytest", "-q"])
        if args.all_checks or args.frontend:
            run(repo_root / "services/web", ["npm", "run", "build"])
        if args.pull:
            run(repo_root, compose_cmd(args, "pull"))
        up_args = ["up", "-d"] if args.no_build else ["up", "-d", "--build"]
        run(repo_root, compose_cmd(args, *up_args))

        wait_for_json("API liveness", f"{args.api_url}/health", args.timeout, args.interval, {"status": "ok"})
        wait_for_json("API readiness", f"{args.api_url}/ready", args.timeout, args.interval, {"status": "ready"})
        wait_for_status("web app", args.web_url, args.timeout, args.interval)
        wait_for_status("MinIO", f"{args.minio_url}/minio/health/live", args.timeout, args.interval)

        if not args.skip_smoke:
            run_smoke_test(args)

        print("\nNeuroDocOps stack is running.")
        print(f"API:           {args.api_url}")
        print(f"Web:           {args.web_url}")
        print(f"MinIO:         {args.minio_url}")
        print(f"MinIO console: {args.minio_console_url}")
        print("\nLogs:")
        print(" ".join(compose_cmd(args, "logs", "--follow")))
        print("\nStop:")
        print(" ".join(compose_cmd(args, "down")))
        if args.tail_logs:
            run(repo_root, compose_cmd(args, "logs", "--follow"))
        return 0
    except Exception as exc:
        print(f"\nOrchestration failed: {exc}", file=sys.stderr)
        if args.logs_on_failure:
            subprocess.run(compose_cmd(args, "logs"), cwd=repo_root, check=False)
        if args.down_on_failure:
            subprocess.run(compose_cmd(args, "down"), cwd=repo_root, check=False)
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start NeuroDocOps, run an E2E smoke test, and keep services up.")
    parser.add_argument("--compose-file", default="infra/docker-compose.yml")
    parser.add_argument("--project-name", default="neurodocops")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--web-url", default="http://localhost:5173")
    parser.add_argument("--minio-url", default="http://localhost:9000")
    parser.add_argument("--minio-console-url", default="http://localhost:9001")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--pull", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--unit", action="store_true")
    parser.add_argument("--frontend", action="store_true")
    parser.add_argument("--all-checks", action="store_true")
    parser.add_argument("--tail-logs", action="store_true")
    parser.add_argument("--logs-on-failure", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--down-on-failure", action="store_true")
    return parser.parse_args()


def compose_cmd(args: argparse.Namespace, *extra: str) -> list[str]:
    return ["docker", "compose", "-f", args.compose_file, "-p", args.project_name, *extra]


def run(cwd: Path, command: list[str]) -> None:
    print(f"\n$ {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def request_json(method: str, url: str, payload: dict[str, object] | None = None, timeout: int = 10) -> tuple[int, object]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        return response.status, json.loads(raw) if raw else None


def request_status(url: str, timeout: int = 10) -> int:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        response.read()
        return response.status


def wait_for_json(description: str, url: str, timeout: int, interval: float, expected: dict[str, str]) -> object:
    def predicate() -> object | None:
        status_code, body = request_json("GET", url)
        if status_code == 200 and isinstance(body, dict) and all(body.get(key) == value for key, value in expected.items()):
            return body
        return None

    return wait_until(description, timeout, interval, predicate)


def wait_for_status(description: str, url: str, timeout: int, interval: float, expected_status: int = 200) -> int:
    def predicate() -> int | None:
        status_code = request_status(url)
        return status_code if status_code == expected_status else None

    return wait_until(description, timeout, interval, predicate)


def wait_until(description: str, timeout: int, interval: float, predicate):
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result:
                print(f"{description}: ready")
                return result
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            last_error = exc
        time.sleep(interval)
    raise RuntimeError(f"Timed out waiting for {description}: {last_error}")


def run_smoke_test(args: argparse.Namespace) -> None:
    reference = f"CLM-SMOKE-{int(time.time())}"
    print(f"\nRunning queued workflow smoke test for {reference}")
    packet_payload = {
        "claim_reference": reference,
        "claimant_name": "Smoke Test Claimant",
        "loss_type": "auto",
        "documents": [
            {"filename": "claim-form.pdf", "text": f"Claim form for claim number {reference} and policy number POL-SMOKE-42. Loss date 2026-05-01."},
            {"filename": "incident-report.pdf", "text": "Incident report for accident with loss date 2026-05-01 at North Bridge Road."},
            {"filename": "identity.pdf", "text": "Passport identity document for claimant Smoke Test Claimant."},
            {"filename": "repair-invoice.pdf", "text": "Repair invoice for vehicle damage. Amount due 1250 USD."},
        ],
        "metadata": {"source": "orchestrator-smoke-test"},
    }
    status_code, packet = request_json("POST", f"{args.api_url}/claim-packets", packet_payload)
    assert_equal(status_code, 201, "packet create status")
    assert_true(isinstance(packet, dict), "packet create returned JSON object")
    packet_id = packet["id"]
    assert_equal(packet["status"], "intaked", "packet initial status")
    assert_equal(len(packet["documents"]), 4, "packet document count")

    status_code, job = request_json("POST", f"{args.api_url}/claim-packets/{packet_id}/process", {"steps": ["classify", "extract", "checklist"]})
    assert_equal(status_code, 202, "job enqueue status")
    assert_true(isinstance(job, dict), "job enqueue returned JSON object")
    job_id = job["id"]
    assert_equal(job["status"], "queued", "job initial status")

    def job_done() -> dict[str, object] | None:
        _, body = request_json("GET", f"{args.api_url}/jobs/{job_id}")
        assert_true(isinstance(body, dict), "job status returned JSON object")
        if body["status"] == "failed":
            raise RuntimeError(f"Worker job failed: {body.get('error')}")
        return body if body["status"] == "succeeded" else None

    wait_until("worker job", args.timeout, args.interval, job_done)
    _, processed = request_json("GET", f"{args.api_url}/claim-packets/{packet_id}")
    assert_true(isinstance(processed, dict), "processed packet returned JSON object")
    assert_equal(processed["status"], "needs_review", "processed packet status")
    assert_true(processed["checklist"], "checklist exists")
    assert_true(processed["review_tasks"], "review tasks exist")
    assert_true(any(document["document_type"] != "unknown" for document in processed["documents"]), "documents classified")
    assert_true(any(document["extracted_fields"] for document in processed["documents"]), "fields extracted")

    _, approved = request_json(
        "POST",
        f"{args.api_url}/claim-packets/{packet_id}/review",
        {"decision": "approve", "reviewer": "orchestrator@example.com", "notes": "Smoke test approval."},
    )
    assert_true(isinstance(approved, dict), "review returned JSON object")
    assert_equal(approved["status"], "approved", "approved packet status")
    assert_true(all(task["status"] == "resolved" for task in approved["review_tasks"]), "review tasks resolved")

    _, exported = request_json("POST", f"{args.api_url}/claim-packets/{packet_id}/export")
    assert_true(isinstance(exported, dict), "export returned JSON object")
    assert_equal(exported["status"], "exported", "export status")
    assert_equal(exported["open_review_tasks"], 0, "open review task count")
    assert_equal(exported["document_count"], 4, "export document count")
    assert_true(exported["documents"], "export documents included")

    _, audit = request_json("GET", f"{args.api_url}/claim-packets/{packet_id}/audit")
    assert_true(isinstance(audit, list), "audit returned JSON list")
    actions = [event["action"] for event in audit]
    assert_equal(actions[-6:], ["packet_intaked", "documents_classified", "fields_extracted", "checklist_evaluated", "review_completed", "packet_exported"], "audit action sequence")
    print("Smoke test: passed")


def assert_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def assert_true(value: object, label: str) -> None:
    if not value:
        raise AssertionError(label)


if __name__ == "__main__":
    raise SystemExit(main())
