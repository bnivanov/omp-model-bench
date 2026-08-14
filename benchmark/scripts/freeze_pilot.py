#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tomllib
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
SOURCE_TASKS = ROOT / "vendor/deep-swe/tasks"
OUTPUT_TASKS = ROOT / "benchmark/tasks"
MANIFEST = ROOT / "benchmark/pilot-manifest.json"

EXPECTED_DEEPSWE_SHA = "435ee89ec2f2e2289f33b0da4f992f0b7b7266b9"
SEED = "omp-deepswe-pilot-v1-2026-08-09"

PILOT_SIZE = 8
SPLIT_SIZE = 4
MAX_PER_LANGUAGE = 2
MAX_PER_REPOSITORY = 1

# Used during infrastructure/network/model smoke testing.
EXCLUDED_TASK_IDS = {
    "abs-module-cache-flags",
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def repo_key(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return path.lower()


def load_pool() -> list[dict]:
    pool = []

    for toml_path in sorted(SOURCE_TASKS.glob("*/task.toml")):
        with toml_path.open("rb") as f:
            data = tomllib.load(f)

        meta = data.get("metadata", {})

        task_id = meta.get("task_id")
        language = meta.get("language")
        repository_url = meta.get("repository_url")
        category = meta.get("category")

        if not task_id or not language or not repository_url:
            raise RuntimeError(
                f"Missing required metadata in {toml_path}"
            )

        if task_id in EXCLUDED_TASK_IDS:
            continue

        rank_hash = sha256_text(f"{SEED}\0{task_id}")

        pool.append(
            {
                "task_id": task_id,
                "language": language.lower(),
                "repository_url": repository_url,
                "repository": repo_key(repository_url),
                "category": category,
                "source_dir": toml_path.parent,
                "rank_hash": rank_hash,
            }
        )

    return sorted(pool, key=lambda x: (x["rank_hash"], x["task_id"]))


def select_tasks(pool: list[dict]) -> list[dict]:
    selected = []
    language_counts = Counter()
    repository_counts = Counter()

    for task in pool:
        if language_counts[task["language"]] >= MAX_PER_LANGUAGE:
            continue

        if repository_counts[task["repository"]] >= MAX_PER_REPOSITORY:
            continue

        selected.append(task)
        language_counts[task["language"]] += 1
        repository_counts[task["repository"]] += 1

        if len(selected) == PILOT_SIZE:
            break

    if len(selected) != PILOT_SIZE:
        raise RuntimeError(
            f"Could only select {len(selected)} tasks under current constraints"
        )

    return selected


def assign_splits(selected: list[dict]) -> list[dict]:
    splits = {
        "screening": [],
        "holdout": [],
    }
    language_counts = {
        "screening": Counter(),
        "holdout": Counter(),
    }

    for task in selected:
        candidates = [
            split
            for split in ("screening", "holdout")
            if len(splits[split]) < SPLIT_SIZE
        ]

        split = min(
            candidates,
            key=lambda s: (
                language_counts[s][task["language"]],
                len(splits[s]),
                0 if s == "screening" else 1,
            ),
        )

        copy = dict(task)
        copy["split"] = split
        splits[split].append(copy)
        language_counts[split][task["language"]] += 1

    ordered = splits["screening"] + splits["holdout"]

    for index, task in enumerate(ordered, start=1):
        task["pilot_index"] = index

    return ordered


def force_allow_internet_false(text: str) -> str:
    header = re.search(r"(?m)^\[environment\]\s*$", text)

    if not header:
        raise RuntimeError("task.toml has no [environment] section")

    section_start = header.end()
    next_header = re.search(
        r"(?m)^\[[^\]]+\]\s*$",
        text[section_start:],
    )

    section_end = (
        section_start + next_header.start()
        if next_header
        else len(text)
    )

    section = text[section_start:section_end]

    if re.search(r"(?m)^allow_internet\s*=", section):
        section = re.sub(
            r"(?m)^allow_internet\s*=.*$",
            "allow_internet = false",
            section,
            count=1,
        )
        text = text[:section_start] + section + text[section_end:]
    else:
        text = (
            text[:header.end()]
            + "\nallow_internet = false"
            + text[header.end():]
        )

    parsed = tomllib.loads(text)

    if parsed["environment"].get("allow_internet") is not False:
        raise RuntimeError("Failed to force environment.allow_internet=false")

    return text


def print_preview(tasks: list[dict], pool_size: int) -> None:
    print(f"DeepSWE SHA: {EXPECTED_DEEPSWE_SHA}")
    print(f"Seed:        {SEED}")
    print(f"Eligible:    {pool_size}")
    print(f"Pilot:       {len(tasks)}")
    print()

    print(
        f"{'#':<3} {'split':<10} {'language':<12} "
        f"{'repository':<34} task"
    )
    print("-" * 105)

    for task in tasks:
        print(
            f"{task['pilot_index']:<3} "
            f"{task['split']:<10} "
            f"{task['language']:<12} "
            f"{task['repository']:<34} "
            f"{task['task_id']}"
        )

    print()
    print("LANGUAGE COUNTS")
    for language, count in sorted(
        Counter(t["language"] for t in tasks).items()
    ):
        print(f"  {language}: {count}")

    print()
    print("REPOSITORIES")
    for repository in sorted(t["repository"] for t in tasks):
        print(f"  {repository}")


def freeze(tasks: list[dict]) -> None:
    if MANIFEST.exists():
        raise RuntimeError(
            f"{MANIFEST} already exists; refusing to overwrite frozen pilot"
        )

    existing = list(OUTPUT_TASKS.iterdir()) if OUTPUT_TASKS.exists() else []
    if existing:
        raise RuntimeError(
            f"{OUTPUT_TASKS} is not empty; refusing to overwrite it"
        )

    OUTPUT_TASKS.mkdir(parents=True, exist_ok=True)

    manifest_tasks = []

    for task in tasks:
        source = task["source_dir"]
        destination = OUTPUT_TASKS / task["task_id"]

        shutil.copytree(source, destination)

        source_toml = source / "task.toml"
        frozen_toml = destination / "task.toml"

        original_text = frozen_toml.read_text()
        frozen_text = force_allow_internet_false(original_text)
        frozen_toml.write_text(frozen_text)

        manifest_tasks.append(
            {
                "pilot_index": task["pilot_index"],
                "split": task["split"],
                "task_id": task["task_id"],
                "language": task["language"],
                "category": task["category"],
                "repository": task["repository"],
                "repository_url": task["repository_url"],
                "source_relative_path": str(
                    source.relative_to(ROOT)
                ),
                "frozen_relative_path": str(
                    destination.relative_to(ROOT)
                ),
                "selection_rank_sha256": task["rank_hash"],
                "source_task_toml_sha256": file_sha256(source_toml),
                "frozen_task_toml_sha256": file_sha256(frozen_toml),
                "allow_internet": False,
            }
        )

    manifest = {
        "schema_version": 1,
        "deep_swe_commit": EXPECTED_DEEPSWE_SHA,
        "seed": SEED,
        "selection": {
            "pilot_size": PILOT_SIZE,
            "screening_size": SPLIT_SIZE,
            "holdout_size": SPLIT_SIZE,
            "max_per_language": MAX_PER_LANGUAGE,
            "max_per_repository": MAX_PER_REPOSITORY,
            "ranking": "sha256(seed + NUL + task_id)",
            "excluded_task_ids": sorted(EXCLUDED_TASK_IDS),
        },
        "tasks": manifest_tasks,
    }

    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")

    print()
    print(f"Frozen tasks written to: {OUTPUT_TASKS}")
    print(f"Manifest written to:     {MANIFEST}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--freeze",
        action="store_true",
        help="Copy selected tasks and write the frozen manifest",
    )
    args = parser.parse_args()

    actual_sha = git_head(ROOT / "vendor/deep-swe")

    if actual_sha != EXPECTED_DEEPSWE_SHA:
        raise RuntimeError(
            "DeepSWE revision mismatch:\n"
            f"  expected {EXPECTED_DEEPSWE_SHA}\n"
            f"  actual   {actual_sha}"
        )

    pool = load_pool()
    selected = select_tasks(pool)
    tasks = assign_splits(selected)

    print_preview(tasks, len(pool))

    if args.freeze:
        freeze(tasks)
    else:
        print()
        print("PREVIEW ONLY — nothing copied or frozen.")


if __name__ == "__main__":
    main()
