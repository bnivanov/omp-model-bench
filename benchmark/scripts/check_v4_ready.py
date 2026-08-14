#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "benchmark/architectures.json"
FROZEN = ROOT / "benchmark/frozen-versions.txt"
CHECKSUMS = ROOT / "benchmark/bin/SHA256SUMS"
HOST_OMP = ROOT / "benchmark/bin/omp-darwin-arm64"
FROZEN_OMP_VERSION = "17.2.15"
EXPECTED_CONDITIONS = {
    "ds4-solo",
    "k3-plan-yolo-ds4",
    "k3-prewalk-ds4",
    "ds4-k3-advisor",
    "ds4-k3-review-ds4",
    "k3-plan-yolo-ds4-k3-review",
    "ds4-luna-advisor",
    "k3-prewalk-ds4-k3-review",
    "k3-solo",
}


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)
    print(f"OK  {message}")


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def validate_manifest() -> None:
    manifest = json.loads(MANIFEST.read_text())
    common = manifest["common"]
    conditions = manifest["conditions"]
    check(manifest["schema_version"] == 4, "condition manifest uses schema v4")
    check(set(conditions) == EXPECTED_CONDITIONS, "canonical condition set is exact")
    check(common["thinking"] == "max", "all roles are frozen at Max thinking")
    check(common["subagents"] is False, "implementation subagents are disabled")
    check(common["repair_passes"] == 1, "review has exactly one repair pass")
    check(common["advisor_sync_backlog"] == 1, "advisor sync backlog is frozen to one")
    check(common["advisor_immune_turns"] == 3, "advisor immune turns are frozen to three")
    check(
        common["gateway_providers"] == ["deepseek", "kimi-code", "openai-codex"],
        "gateway providers match the DS4, K3, and exploratory Luna scope",
    )
    for condition_id, condition in conditions.items():
        check(
            condition["phase"] in {"harness", "frontier", "conditional"},
            f"{condition_id} has a valid phase",
        )
        check("/" in condition["worker_model"], f"{condition_id} has a provider-qualified worker")
        check(
            condition.get("prompt_scaffold", "none") == "none",
            f"{condition_id} disables prompt scaffolds",
        )


def validate_constructors() -> None:
    from benchmark.agents.omp_deepswe import OmpDeepSWE

    class Probe(OmpDeepSWE):
        def __init__(self, **kwargs):
            self.model_name = kwargs.get("model_name")
            OmpDeepSWE.__init__(self, **kwargs)

    manifest = json.loads(MANIFEST.read_text())
    common = manifest["common"]
    for condition_id, condition in manifest["conditions"].items():
        kwargs = {
            **common,
            **condition,
            "model_name": condition["worker_model"],
            "logs_dir": ROOT,
        }
        kwargs.pop("phase")
        kwargs.pop("gateway_providers")
        Probe(**kwargs)
        print(f"OK  {condition_id} constructor accepts frozen condition")

    invalid = [
        {"model_name": "deepseek/deepseek-v4-flash", "logs_dir": ROOT, "thinking": "low"},
        {"model_name": "deepseek/deepseek-v4-flash", "logs_dir": ROOT, "subagents": True},
        {"model_name": "deepseek/deepseek-v4-flash", "logs_dir": ROOT, "repair_passes": 2},
        {"model_name": "deepseek/deepseek-v4-flash", "logs_dir": ROOT, "treatment": "advisor"},
        {"model_name": "deepseek/deepseek-v4-flash", "logs_dir": ROOT, "planner_model": "kimi-code/k3"},
    ]
    for kwargs in invalid:
        try:
            Probe(**kwargs)
        except ValueError:
            continue
        raise RuntimeError(f"invalid constructor condition was accepted: {kwargs}")
    print("OK  invalid treatment combinations fail before execution")


def validate_frozen_sources() -> None:
    pins = dict(line.split() for line in FROZEN.read_text().splitlines() if line.strip())
    paths = {"oh-my-pi": ROOT / "vendor/oh-my-pi", "pier": ROOT / "vendor/pier", "deep-swe": ROOT / "vendor/deep-swe"}
    for name, path in paths.items():
        check(git("rev-parse", "HEAD", cwd=path) == pins[name], f"{name} checkout matches frozen revision")
    for line in CHECKSUMS.read_text().splitlines():
        expected, relative = line.split(maxsplit=1)
        path = ROOT / relative.strip()
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        check(actual == expected, f"{relative.strip()} checksum matches")
    host_version = subprocess.check_output([str(HOST_OMP), "--version"], text=True).strip()
    check(
        host_version == f"omp/{FROZEN_OMP_VERSION}",
        "host broker/gateway OMP matches frozen version",
    )


def validate_candidate_patch() -> None:
    with tempfile.TemporaryDirectory(prefix="omp-v4-patch-") as raw:
        repo = Path(raw)
        git("init", "-q", cwd=repo)
        git("config", "user.email", "bench@localhost", cwd=repo)
        git("config", "user.name", "Benchmark", cwd=repo)
        (repo / "modified.txt").write_text("old\n")
        (repo / "deleted.txt").write_text("delete\n")
        (repo / "binary.bin").write_bytes(b"\x00old")
        git("add", "-A", cwd=repo)
        git("commit", "-qm", "base", cwd=repo)
        base = git("rev-parse", "HEAD", cwd=repo)
        (repo / "modified.txt").write_text("new\n")
        (repo / "deleted.txt").unlink()
        (repo / "binary.bin").write_bytes(b"\x00new")
        (repo / "untracked.txt").write_text("new file\n")
        index = repo / "temporary-index"
        env = {**os.environ, "GIT_INDEX_FILE": str(index)}
        subprocess.run(["git", "read-tree", base], cwd=repo, env=env, check=True)
        subprocess.run(["git", "add", "-A"], cwd=repo, env=env, check=True)
        patch = subprocess.check_output(["git", "diff", "--cached", "--binary", base, "--", "."], cwd=repo, env=env, text=True)
        for name in ("modified.txt", "deleted.txt", "binary.bin", "untracked.txt"):
            check(name in patch, f"candidate patch captures {name}")


def validate_repo(require_clean: bool) -> None:
    if require_clean:
        check(git("status", "--porcelain") == "", "repository worktree is clean")
    else:
        print("SKIP repository clean check (--allow-dirty)")
    check(not (ROOT / ".benchmark-v4-backup-20260812-105233").exists(), "obsolete local backup is absent")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    validate_repo(require_clean=not args.allow_dirty)
    validate_manifest()
    validate_constructors()
    validate_frozen_sources()
    validate_candidate_patch()
    print("\nV4_LOCAL_READINESS_OK")


if __name__ == "__main__":
    main()
