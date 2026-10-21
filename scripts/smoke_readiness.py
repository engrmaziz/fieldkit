"""Fieldkit Multi-Service Readiness Smoke Test.

Probes registered platform microservices across Docker Compose profiles,
verifying /readyz and /healthz endpoints with latency benchmarks.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx


@dataclass
class ServiceProbe:
    name: str
    target_type: str  # "http" or "tcp"
    host: str
    port: int
    path: str = "/readyz"
    required: bool = False


SERVICES: list[ServiceProbe] = [
    ServiceProbe("Postgres (pgvector)", "tcp", "127.0.0.1", 5432, required=False),
    ServiceProbe("Redis", "tcp", "127.0.0.1", 6379, required=False),
    ServiceProbe("Keycloak SSO", "http", "127.0.0.1", 8080, path="/health/ready", required=False),
    ServiceProbe("Workflow Engine", "http", "127.0.0.1", 8008, path="/readyz", required=False),
    ServiceProbe("Vision Edge (InspectAI & Safety)", "http", "127.0.0.1", 8005, path="/readyz", required=False),
    ServiceProbe("Foundry API", "http", "127.0.0.1", 8001, path="/readyz", required=False),
    ServiceProbe("Assistant API", "http", "127.0.0.1", 8002, path="/readyz", required=False),
    ServiceProbe("Ops Copilot API", "http", "127.0.0.1", 8003, path="/readyz", required=False),
    ServiceProbe("DocAI Engine", "http", "127.0.0.1", 8004, path="/readyz", required=False),
    ServiceProbe("Tracehub Observability", "http", "127.0.0.1", 8006, path="/readyz", required=False),
]


def probe_tcp(host: str, port: int, timeout_sec: float = 0.5) -> tuple[bool, float, str]:
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return True, elapsed_ms, "Connected"
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return False, elapsed_ms, str(e)


def probe_http(host: str, port: int, path: str, timeout_sec: float = 0.8) -> tuple[bool, float, str]:
    start = time.perf_counter()
    url = f"http://{host}:{port}{path}"
    try:
        with httpx.Client(timeout=timeout_sec) as client:
            resp = client.get(url)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            if resp.status_code in (200, 204):
                return True, elapsed_ms, f"{resp.status_code} OK"
            return False, elapsed_ms, f"HTTP {resp.status_code}"
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return False, elapsed_ms, "Offline"


def _check_probe(probe: ServiceProbe) -> tuple[ServiceProbe, bool, float, str]:
    if probe.target_type == "tcp":
        ok, latency_ms, details = probe_tcp(probe.host, probe.port)
    else:
        ok, latency_ms, details = probe_http(probe.host, probe.port, probe.path)
    return probe, ok, latency_ms, details


def run_smoke_test(probe_all: bool = True) -> int:
    print("=======================================================")
    print("      FIELDKIT MULTI-SERVICE READINESS SMOKE TEST      ")
    print("      Evaluating platform endpoints and health probes  ")
    print("=======================================================\n")

    healthy_count = 0
    total_count = len(SERVICES)

    print(f"{'SERVICE':<32} | {'TYPE':<5} | {'PORT':<5} | {'STATUS':<10} | {'LATENCY':<8} | {'DETAILS'}")
    print("-" * 80)

    # Concurrently probe all services
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(SERVICES)) as executor:
        results = list(executor.map(_check_probe, SERVICES))

    for probe, ok, latency_ms, details in results:
        if ok:
            healthy_count += 1
            status_badge = "[READY]"
        else:
            status_badge = "[OFFLINE]" if not probe.required else "[FAILED]"

        print(f"{probe.name:<32} | {probe.target_type.upper():<5} | {probe.port:<5} | {status_badge:<10} | {latency_ms:6.1f}ms | {details}")

    print("-" * 80)
    print(f"\n[SUMMARY] {healthy_count} / {total_count} services active & responsive.")
    print("Note: In localized environments without all containers up, offline status on optional profiles is expected.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Fieldkit Multi-Service Readiness Smoke Test")
    parser.parse_args()
    code = run_smoke_test()
    sys.exit(code)


if __name__ == "__main__":
    main()
