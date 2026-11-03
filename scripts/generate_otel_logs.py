#!/usr/bin/env python3
"""Write synthetic OTEL-shaped JSON logs for Fluent Bit to tail.

Simulates the Kubernetes apps of Helix Clinical Cloud (a fictional life-sciences SaaS
vendor): imaging archive, DICOM router, trial-data upload, eConsent, auth, ingress.
Every line carries the client (pharma / CRO tenant), site, study, end user, and latency.

The run compresses `--simulated-hours` of client traffic into `--duration` seconds of
wall time. Each line's `Timestamp` is its simulated source time; bronze `time` is the
real ingest time. Incidents from src/config/incidents.json are injected so the
anomaly model and incident briefs have ground truth to find.

Default rate is 15 MB/s, the 1.3 TB/day equivalent, for a bounded duration.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import signal
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCIDENTS_PATH = ROOT / "src" / "config" / "incidents.json"

# 1.3 TB/day ≈ 15.046 MB/s
DEFAULT_MBPS = 15.0
MAX_DURATION = 50 * 60

# (service, namespace, weight, median latency ms, url paths)
SERVICES = [
    ("imaging-archive", "imaging", 0.24, 180, ["/studies", "/instances", "/manifests"]),
    ("dicom-router", "imaging", 0.18, 90, ["/dicom/c-store", "/dicom/association"]),
    ("trial-upload-api", "edc", 0.20, 240, ["/uploads", "/uploads/chunk", "/uploads/complete"]),
    ("econsent-web", "consent", 0.12, 150, ["/consent/form", "/consent/sign"]),
    ("auth-api", "identity", 0.14, 40, ["/oauth/token", "/sso/assert"]),
    ("ingress-gateway", "platform", 0.12, 20, ["/health", "/api"]),
]

CLIENTS = [
    ("northwind-bio", "Northwind Bio", ["site-101", "site-102", "site-103"], ["NWB-ONC-301", "NWB-CNS-112"], 0.20),
    ("contoso-tx", "Contoso Therapeutics", ["site-111", "site-112", "site-113"], ["CTX-CV-220", "CTX-RES-014"], 0.18),
    ("fabrikam-cro", "Fabrikam CRO", ["site-201", "site-202", "site-203", "site-204"], ["FAB-ONC-501", "FAB-IMM-077", "FAB-DERM-009"], 0.22),
    ("tailspin-onc", "Tailspin Oncology", ["site-301", "site-302"], ["TSO-ONC-118"], 0.14),
    ("wingtip-gx", "Wingtip Genomics", ["site-401", "site-402"], ["WGX-RARE-031"], 0.12),
    ("adatum-clin", "Adatum Clinical Research", ["site-501", "site-502", "site-503"], ["ADC-NEU-260", "ADC-MET-045"], 0.14),
]

MESSAGES = {
    "imaging-archive": {
        "INFO": ["study stored", "instance stored", "manifest generated"],
        "WARN": ["S3 put slow", "retrying instance write"],
        "ERROR": ["manifest generation failed", "connection reset by peer"],
    },
    "dicom-router": {
        "INFO": ["C-STORE accepted", "association released"],
        "WARN": ["association retry"],
        "ERROR": ["DICOM association rejected", "context deadline exceeded"],
    },
    "trial-upload-api": {
        "INFO": ["upload chunk received", "upload completed"],
        "WARN": ["slow upload chunk"],
        "ERROR": ["upload timeout", "checksum mismatch"],
    },
    "econsent-web": {
        "INFO": ["consent form rendered", "consent signed"],
        "WARN": ["e-signature retry"],
        "ERROR": ["e-signature provider 503"],
    },
    "auth-api": {
        "INFO": ["token issued", "SSO login ok"],
        "WARN": ["MFA challenge timeout"],
        "ERROR": ["SSO assertion invalid"],
    },
    "ingress-gateway": {
        "INFO": ["request completed"],
        "WARN": ["readiness probe failed", "TLS handshake timeout"],
        "ERROR": ["OOMKilled", "upstream 502"],
    },
}
DEBUG_MESSAGES = ["handler entered", "sql query planned"]
SEV_NUMBER = {"DEBUG": 5, "INFO": 9, "WARN": 13, "ERROR": 17}
METHODS = ["GET", "POST", "PUT"]

BASE_ERROR_P = 0.015
BASE_WARN_P = 0.05
DEBUG_P = 0.08


def _hex(n_bytes: int) -> str:
    return os.urandom(n_bytes).hex()


def _weighted(rng: random.Random, items: list, weight_idx: int):
    r = rng.random()
    acc = 0.0
    for item in items:
        acc += item[weight_idx]
        if r <= acc:
            return item
    return items[-1]


def load_incidents(path: Path = INCIDENTS_PATH) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text())["incidents"]


def _active_incident(incidents: list[dict], sim_hour: float, client: str, site: str, service: str) -> dict | None:
    for inc in incidents:
        if not (inc["start_hour"] <= sim_hour < inc["end_hour"]):
            continue
        if inc["client_id"] != client or service not in inc["services"]:
            continue
        if inc["site_ids"] and site not in inc["site_ids"]:
            continue
        return inc
    return None


def make_line(rng: random.Random, event_ns: int, sim_hour: float, incidents: list[dict]) -> bytes:
    service, ns, _, median_ms, paths = _weighted(rng, SERVICES, 2)
    client_id, client_name, sites, studies, _ = _weighted(rng, CLIENTS, 4)
    site = rng.choice(sites)
    study = rng.choice(studies)
    inc = _active_incident(incidents, sim_hour, client_id, site, service)

    error_p = inc["error_probability"] if inc else BASE_ERROR_P
    warn_p = inc["warn_probability"] if inc else BASE_WARN_P
    r = rng.random()
    if r < error_p:
        sev = "ERROR"
    elif r < error_p + warn_p:
        sev = "WARN"
    elif r < error_p + warn_p + DEBUG_P:
        sev = "DEBUG"
    else:
        sev = "INFO"

    if sev == "DEBUG":
        msg = rng.choice(DEBUG_MESSAGES)
    elif inc and sev == "ERROR":
        msg = rng.choice(inc["error_messages"])
    elif inc and sev == "WARN" and inc.get("warn_messages"):
        msg = rng.choice(inc["warn_messages"])
    else:
        msg = rng.choice(MESSAGES[service][sev])

    latency = rng.lognormvariate(0, 0.45) * median_ms
    if inc:
        latency *= inc["latency_multiplier"]
    if sev == "ERROR":
        status = rng.choice([500, 503, 504])
    elif sev == "WARN":
        status = rng.choice([200, 429])
    else:
        status = 200

    method = rng.choice(METHODS)
    path = rng.choice(paths)
    record_id = _hex(16)
    user = f"coordinator{rng.randint(1, 40)}@{client_id}.example"
    # Keep a stable ~1KB envelope so --mbps maps cleanly to row rate.
    pad = "x" * 380
    line = (
        "{"
        f'"message":"{method} {path} {status} {msg} client={client_id} site={site} {record_id}",'
        f'"service.name":"{service}",'
        f'"k8s.namespace.name":"{ns}",'
        f'"deployment":"{service}",'
        f'"helix.client_id":"{client_id}",'
        f'"helix.client_name":"{client_name}",'
        f'"helix.site_id":"{site}",'
        f'"helix.study_id":"{study}",'
        f'"enduser.id":"{user}",'
        f'"latency_ms":{latency:.1f},'
        f'"SeverityText":"{sev}",'
        f'"SeverityNumber":"{SEV_NUMBER[sev]}",'
        f'"TraceId":"{_hex(16)}",'
        f'"SpanId":"{_hex(8)}",'
        f'"record_id":"{record_id}",'
        f'"http.method":"{method}",'
        f'"url.path":"{path}",'
        f'"http.status_code":{status},'
        f'"Timestamp":{event_ns},'
        f'"ObservedTimestamp":{event_ns},'
        f'"pad":"{pad}"'
        "}\n"
    )
    return line.encode()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=os.environ.get("LOG_PATH", str(ROOT / "logs" / "otel.jsonl")))
    parser.add_argument("--mbps", type=float, default=DEFAULT_MBPS)
    parser.add_argument("--duration", type=int, default=300, help="seconds (capped at 50 min)")
    parser.add_argument(
        "--simulated-hours",
        type=float,
        default=float(os.environ.get("SIM_HOURS", "24")),
        help="hours of client traffic compressed into the run; 0 = real time",
    )
    parser.add_argument("--fifo", action="store_true", help="create path as a FIFO if missing")
    args = parser.parse_args()
    duration = min(max(1, args.duration), MAX_DURATION)
    mbps = max(0.1, args.mbps)
    target_bps = mbps * 1_000_000
    incidents = load_incidents()

    path = Path(args.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if args.fifo:
        if path.exists() and not path.is_fifo():
            raise SystemExit(f"{path} exists and is not a FIFO")
        if not path.exists():
            os.mkfifo(path, 0o600)
        fh = open(path, "wb", buffering=0)
    else:
        fh = open(path, "ab", buffering=1024 * 1024)

    rng = random.Random()
    sent_bytes = 0
    sent_rows = 0
    start = time.perf_counter()
    end = start + duration
    sim_hours = max(0.0, args.simulated_hours)
    sim_span_ns = int(sim_hours * 3600 * 1e9)
    wall_start_ns = time.time_ns()
    sim_start_ns = wall_start_ns - sim_span_ns

    def _stop(_signum=None, _frame=None):
        raise TimeoutError("duration elapsed")

    signal.signal(signal.SIGALRM, _stop)
    signal.alarm(duration)
    print(
        f"simulating {sim_hours:g}h of traffic in {duration}s at {mbps:g} MB/s; "
        f"{len(incidents)} injected incidents",
        flush=True,
    )
    try:
        while True:
            now = time.perf_counter()
            if now >= end:
                break
            elapsed = now - start
            if sim_span_ns:
                frac = elapsed / duration
                event_ns = sim_start_ns + int(frac * sim_span_ns)
                sim_hour = frac * sim_hours
            else:
                event_ns = time.time_ns()
                sim_hour = 0.0
            batch = bytearray()
            # ~64 KB batches keep syscall rate reasonable at 15 MB/s
            while len(batch) < 64 * 1024:
                batch += make_line(rng, event_ns + rng.randint(0, 999_999), sim_hour, incidents)
            fh.write(batch)
            sent_bytes += len(batch)
            sent_rows += batch.count(b"\n")
            expected = target_bps * max(elapsed, 1e-6)
            if sent_bytes > expected:
                time.sleep((sent_bytes - expected) / target_bps)
        fh.flush()
    except (BrokenPipeError, TimeoutError):
        pass
    finally:
        signal.alarm(0)
        fh.close()
    elapsed = max(time.perf_counter() - start, 1e-6)
    print(
        f"wrote {sent_rows} rows / {sent_bytes / 1_000_000:.1f} MB in {elapsed:.1f}s "
        f"({sent_bytes / elapsed / 1_000_000:.1f} MB/s)"
    )


if __name__ == "__main__":
    main()
