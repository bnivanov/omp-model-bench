#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UV = Path.home() / "AgentWork/bin/uv"
RUNS = ROOT / "benchmark/runs/v4"
CONDITIONS = ROOT / "benchmark/architectures.json"
HOST_OMP = ROOT / "benchmark/bin/omp-darwin-arm64"
FROZEN_OMP_VERSION = "17.2.15"
NETWORK_SMOKE_NAME = "v4-network-isolation-smoke"


def load(path):
    return json.loads(path.read_text())


def git_clean():
    return subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    ).strip() == ""

def host_omp_check():
    version = subprocess.check_output([str(HOST_OMP), "--version"], text=True).strip()
    if version != f"omp/{FROZEN_OMP_VERSION}":
        raise RuntimeError(
            f"host auth infrastructure must use omp/{FROZEN_OMP_VERSION}; observed {version}"
        )


def gateway_check():
    with urllib.request.urlopen("http://127.0.0.1:4000/healthz", timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"gateway health returned {response.status}")


def gateway_token():
    return subprocess.check_output(
        [str(HOST_OMP), "auth-gateway", "token"], cwd=ROOT, text=True
    ).strip()


def matrix():
    manifest = load(CONDITIONS)
    pilot = load(ROOT / "benchmark/pilot-manifest.json")
    tasks = sorted(
        (task for task in pilot["tasks"] if task["split"] == "screening"),
        key=lambda task: task["pilot_index"],
    )
    return [
        (task, condition_id, condition, manifest["common"])
        for task in tasks
        for condition_id, condition in manifest["conditions"].items()
    ]


def job_name(task_index, condition_id):
    return f"v4-t{task_index:02d}-{condition_id}"


def make_models_yaml(common, token):
    lines = ["# Temporary benchmark gateway routing.", "providers:"]
    for provider in common["gateway_providers"]:
        lines.extend(
            [
                f"  {provider}:",
                "    baseUrl: http://host.docker.internal:4000",
                "    auth: oauth",
                "    transport: pi-native",
                f"    apiKey: {token}",
            ]
        )
    fd, path = tempfile.mkstemp(prefix="omp-bench-models-", suffix=".yml")
    os.close(fd)
    Path(path).write_text("\n".join(lines) + "\n")
    os.chmod(path, 0o600)
    return Path(path)


def benchmark_env(common, models_file):
    env = os.environ.copy()
    env.update(
        {
            "OMP_BENCH_INSTALL": "binary",
            "OMP_BENCH_BINARY_ARM64": str((ROOT / "benchmark/bin/omp-linux-arm64").resolve()),
            "OMP_BENCH_BINARY_X64": str((ROOT / "benchmark/bin/omp-linux-x64").resolve()),
            "OMP_BENCH_MODELS_YAML": str(models_file),
            "OMP_BENCH_GATEWAY": "1",
            "OMP_BENCH_GATEWAY_URL": "http://host.docker.internal:4000",
            "OMP_BENCH_GATEWAY_PROVIDERS": ",".join(common["gateway_providers"]),
            "OMP_BENCH_THINKING": common["thinking"],
            "OMP_BENCH_AUTO_APPROVE": "1",
            "OMP_BENCH_WEB_SEARCH": "0",
            "OMP_BENCH_MAX_SPAWNS": "0",
            "OMP_BENCH_ALLOWED_AGENT": "",
        }
    )
    return env


def run_network_smoke(task, common):
    job_dir = RUNS / NETWORK_SMOKE_NAME
    if job_dir.exists():
        shutil.rmtree(job_dir)
    host_omp_check()
    gateway_check()
    models_file = make_models_yaml(common, gateway_token())
    env = benchmark_env(common, models_file)
    task_path = ROOT / "benchmark/tasks" / task["task_id"]
    cmd = [
        str(UV), "run", "--project", "vendor/pier", "--python", "3.12", "--frozen",
        "pier", "run", "--job-name", NETWORK_SMOKE_NAME,
        "--jobs-dir", str(RUNS.relative_to(ROOT)), "--n-attempts", "1",
        "--n-concurrent", "1", "--max-retries", "0", "--agent-import-path",
        "benchmark.agents.omp_deepswe:OmpNetworkSmoke", "--model",
        "deepseek/deepseek-v4-flash", "--env", "docker", "--delete", "--yes",
        "--path", str(task_path.relative_to(ROOT)),
    ]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, env=env)
    finally:
        models_file.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Network isolation smoke failed with exit code {proc.returncode}")
    outputs = list(job_dir.glob("**/agent/network-smoke.txt"))
    if len(outputs) != 1:
        raise RuntimeError(f"Expected one network smoke output, found {len(outputs)}")
    expected = {
        "gateway_allowed=True",
        "external_dns_allowed=False",
        "external_ip_allowed=False",
        "NETWORK_ISOLATION_OK",
    }
    observed = set(outputs[0].read_text().splitlines())
    missing = expected - observed
    if missing:
        raise RuntimeError(f"Network isolation smoke missing evidence: {sorted(missing)}")
    print("NETWORK_ISOLATION_OK")


def agent_kwargs(condition, common):
    values = {
        "treatment": condition["treatment"],
        "worker_model": condition["worker_model"],
        "planner_model": condition.get("planner_model"),
        "prewalker_model": condition.get("prewalker_model"),
        "advisor_model": condition.get("advisor_model"),
        "reviewer_model": condition.get("reviewer_model"),
        "prompt_scaffold": condition.get("prompt_scaffold", "none"),
        "thinking": common["thinking"],
        "advisor_sync_backlog": common["advisor_sync_backlog"],
        "advisor_immune_turns": common["advisor_immune_turns"],
        "repair_passes": common["repair_passes"],
        "subagents": common["subagents"],
    }
    args = []
    for key, value in values.items():
        if value is None:
            continue
        args.extend(["--agent-kwarg", f"{key}={json.dumps(value)}"])
    return args


def run_one(task, condition_id, condition, common, force):
    name = job_name(task["pilot_index"], condition_id)
    job_dir = RUNS / name
    if job_dir.exists():
        if not force:
            print(f"SKIP {name}: already exists")
            return
        shutil.rmtree(job_dir)

    host_omp_check()
    gateway_check()
    models_file = make_models_yaml(common, gateway_token())
    env = benchmark_env(common, models_file)
    task_path = ROOT / "benchmark/tasks" / task["task_id"]
    cmd = [
        str(UV), "run", "--project", "vendor/pier", "--python", "3.12", "--frozen",
        "pier", "run", "--job-name", name, "--jobs-dir", str(RUNS.relative_to(ROOT)),
        "--n-attempts", "1", "--n-concurrent", "1", "--max-retries", "0",
        "--agent-import-path", "benchmark.agents.omp_deepswe:OmpDeepSWE",
        "--model", condition["worker_model"], *agent_kwargs(condition, common),
        "--env", "docker", "--delete", "--enable-verification", "--yes", "--path",
        str(task_path.relative_to(ROOT)),
    ]
    print(f"{name}: {condition['treatment']} worker={condition['worker_model']}")
    try:
        proc = subprocess.run(cmd, cwd=ROOT, env=env)
    finally:
        models_file.unlink(missing_ok=True)
    if not job_dir.exists():
        raise RuntimeError(f"Pier did not create expected job directory: {job_dir}")

    contract = {
        "schema_version": 4,
        "task_index": task["pilot_index"],
        "task_id": task["task_id"],
        "condition_id": condition_id,
        "condition": condition,
        "common": common,
        "pier_return_code": proc.returncode,
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    }
    (job_dir / "run-contract.json").write_text(json.dumps(contract, indent=2) + "\n")
    validation = subprocess.run(
        [str(UV), "run", "--python", "3.12", "python", "benchmark/scripts/validate_run.py",
         "--job-dir", str(job_dir), "--condition", condition_id, "--task-index", str(task["pilot_index"])],
        cwd=ROOT,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Pier failed for {name} with exit code {proc.returncode}")
    if validation.returncode != 0:
        raise RuntimeError(f"Harness validation failed for {name}")


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true")
    mode.add_argument("--run-one", nargs=2, metavar=("TASK_INDEX", "CONDITION"))
    mode.add_argument("--network-smoke", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    rows = matrix()
    if args.network_smoke:
        if not git_clean():
            raise SystemExit("Refusing network smoke: git worktree is not clean.")
        RUNS.mkdir(parents=True, exist_ok=True)
        run_network_smoke(rows[0][0], rows[0][3])
        return
    if not args.run_one:
        for task, condition_id, condition, _ in rows:
            print(f"{task['pilot_index']:<3} {condition_id:<34} {condition['phase']:<11} {condition['treatment']}")
        return
    if not git_clean():
        raise SystemExit("Refusing benchmark run: git worktree is not clean.")
    index, condition_id = int(args.run_one[0]), args.run_one[1]
    selected = [row for row in rows if row[0]["pilot_index"] == index and row[1] == condition_id]
    if len(selected) != 1:
        raise SystemExit(f"No v4 condition for task={index}, condition={condition_id}")
    RUNS.mkdir(parents=True, exist_ok=True)
    run_one(*selected[0], force=args.force)


if __name__ == "__main__":
    main()
