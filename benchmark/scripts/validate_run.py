#!/usr/bin/env python3

import argparse
import hashlib
import json
import math
import re
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    return json.loads(path.read_text())


def assistant_models(path):
    models = set()
    errors = []
    malformed = 0
    for raw in path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(raw)
        except Exception:
            malformed += 1
            continue
        if event.get("type") != "message_end":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        provider, model = message.get("provider"), message.get("model")
        if isinstance(provider, str) and isinstance(model, str):
            models.add(f"{provider}/{model}")
        if message.get("stopReason") == "error" or message.get("errorMessage"):
            errors.append(
                {
                    "provider": provider,
                    "model": model,
                    "error": message.get("errorMessage"),
                }
            )
    return sorted(models), errors, malformed


def session_assistant_evidence(path):
    models = set()
    errors = []
    tool_calls = {}
    malformed = 0
    for raw in path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(raw)
        except Exception:
            malformed += 1
            continue
        if event.get("type") != "message":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        provider, model = message.get("provider"), message.get("model")
        if isinstance(provider, str) and isinstance(model, str):
            models.add(f"{provider}/{model}")
        if message.get("stopReason") == "error" or message.get("errorMessage"):
            errors.append(
                {
                    "provider": provider,
                    "model": model,
                    "error": message.get("errorMessage"),
                }
            )
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "toolCall":
                continue
            name = item.get("name")
            if isinstance(name, str):
                tool_calls[name] = tool_calls.get(name, 0) + 1
    return sorted(models), errors, tool_calls, malformed


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_result(job_dir, condition, violations, evidence):
    result_path = job_dir / "result.json"
    if not result_path.exists():
        violations.append("result.json missing")
        return False

    top = load(result_path)
    stats = top.get("stats")
    if not isinstance(stats, dict):
        violations.append("result.json stats missing")
    else:
        expected_counts = {
            "n_total_trials": 1,
            "n_completed_trials": 1,
            "n_running_trials": 0,
            "n_pending_trials": 0,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        }
        for key, expected in expected_counts.items():
            actual = top.get(key) if key == "n_total_trials" else stats.get(key)
            if actual != expected:
                violations.append(f"result.json {key}={actual!r}, expected {expected}")

    trial_results = list(job_dir.glob("*/result.json"))
    if len(trial_results) != 1:
        violations.append(f"expected one trial result, found {len(trial_results)}")
        return False

    trial = load(trial_results[0])
    exception = trial.get("exception_info")
    model_timeout = False
    if exception is not None:
        if not isinstance(exception, dict):
            violations.append("trial exception_info is malformed")
        elif exception.get("exception_type") == "AgentTimeoutError":
            message = exception.get("exception_message")
            agent_execution = trial.get("agent_execution")
            duration = None
            if isinstance(agent_execution, dict):
                try:
                    started = datetime.fromisoformat(
                        agent_execution["started_at"].replace("Z", "+00:00")
                    )
                    finished = datetime.fromisoformat(
                        agent_execution["finished_at"].replace("Z", "+00:00")
                    )
                    duration = (finished - started).total_seconds()
                except (KeyError, TypeError, ValueError):
                    pass
            if message != "Agent execution timed out after 5400.0 seconds":
                violations.append(f"unexpected agent timeout message: {message!r}")
            elif duration is None or not 5395 <= duration <= 5450:
                violations.append(
                    f"agent timeout duration {duration!r}s is inconsistent with 5400s budget"
                )
            else:
                model_timeout = True
                evidence["model_timeout"] = {
                    "type": exception["exception_type"],
                    "message": message,
                    "agent_execution_seconds": duration,
                }
        else:
            violations.append(
                f"trial failed with {exception.get('exception_type')}: "
                f"{exception.get('exception_message')}"
            )

    if isinstance(stats, dict):
        expected_errors = 1 if exception is not None else 0
        if stats.get("n_errored_trials") != expected_errors:
            violations.append(
                f"result.json n_errored_trials={stats.get('n_errored_trials')!r}, "
                f"expected {expected_errors}"
            )

    agent_result = trial.get("agent_result")
    if not isinstance(agent_result, dict):
        violations.append("trial agent_result missing")
        return model_timeout
    metadata = agent_result.get("metadata")
    stages = metadata.get("stages") if isinstance(metadata, dict) else None
    if not isinstance(stages, dict):
        violations.append("stage accounting metadata missing")
        return model_timeout

    if condition["treatment"] == "advisor" and set(stages) != {"worker", "advisor"}:
        violations.append(
            f"advisor accounting stages are {sorted(stages)}, expected ['advisor', 'worker']"
        )

    required_usage = {
        "input_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "output_tokens",
        "cost_usd",
    }
    if any(
        not isinstance(usage, dict) or not required_usage.issubset(usage)
        for usage in stages.values()
    ):
        violations.append("stage accounting contains malformed usage")
        return model_timeout

    input_tokens = sum(
        usage["input_tokens"] + usage["cache_read_tokens"] for usage in stages.values()
    )
    cache_tokens = sum(usage["cache_read_tokens"] for usage in stages.values())
    output_tokens = sum(usage["output_tokens"] for usage in stages.values())
    cost_usd = sum(usage["cost_usd"] for usage in stages.values())
    reported = {
        "input_tokens": agent_result.get("n_input_tokens"),
        "cache_tokens": agent_result.get("n_cache_tokens"),
        "output_tokens": agent_result.get("n_output_tokens"),
        "cost_usd": agent_result.get("cost_usd") or 0.0,
    }
    expected = {
        "input_tokens": input_tokens,
        "cache_tokens": cache_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
    }
    for key in ("input_tokens", "cache_tokens", "output_tokens"):
        if reported[key] != expected[key]:
            violations.append(
                f"stage {key} total {expected[key]} does not match reported {reported[key]}"
            )
    if not math.isclose(reported["cost_usd"], expected["cost_usd"], abs_tol=1e-12):
        violations.append(
            f"stage cost total {expected['cost_usd']} does not match "
            f"reported {reported['cost_usd']}"
        )
    evidence["stage_accounting"] = {"reported": reported, "summed": expected}
    return model_timeout


def validate_finalization(job_dir, model_timeout, violations, evidence):
    matches = list(job_dir.glob("**/agent/finalization.json"))
    if len(matches) != 1:
        violations.append(f"expected one finalization record, found {len(matches)}")
        return
    finalization = load(matches[0])
    commit_pattern = re.compile(r"^[0-9a-f]{40}$")
    base_commit = finalization.get("base_commit")
    final_commit = finalization.get("final_commit")
    recovered_stash = finalization.get("recovered_cancelled_stash")
    if not isinstance(base_commit, str) or not commit_pattern.fullmatch(base_commit):
        violations.append("finalization base_commit is malformed")
    if not isinstance(final_commit, str) or not commit_pattern.fullmatch(final_commit):
        violations.append("finalization final_commit is malformed")
    if recovered_stash is not None and (
        not isinstance(recovered_stash, str)
        or not commit_pattern.fullmatch(recovered_stash)
    ):
        violations.append("finalization recovered stash is malformed")
    if recovered_stash is not None and not model_timeout:
        violations.append("cancelled stash recovery occurred without a model timeout")
    evidence["finalization"] = finalization


def expected_stages(condition):
    treatment = condition["treatment"]
    if treatment == "solo":
        return {"worker.jsonl": {condition["worker_model"]}}
    if treatment == "plan_yolo":
        return {
            "plan_yolo_worker.jsonl": {
                condition["planner_model"],
                condition["worker_model"],
            }
        }
    if treatment == "prewalk":
        return {
            "prewalk_worker.jsonl": {
                condition["prewalker_model"],
                condition["worker_model"],
            }
        }
    if treatment == "advisor":
        return {"worker.jsonl": {condition["worker_model"]}}
    stages = {
        "worker.jsonl": {condition["worker_model"]},
        "reviewer.jsonl": {condition["reviewer_model"]},
        "repair.jsonl": {condition["worker_model"]},
    }
    if treatment == "plan_yolo_review":
        stages.pop("worker.jsonl")
        stages["plan_yolo_worker.jsonl"] = {
            condition["planner_model"],
            condition["worker_model"],
        }
    if treatment == "prewalk_review":
        stages.pop("worker.jsonl")
        stages["prewalk_worker.jsonl"] = {
            condition["prewalker_model"],
            condition["worker_model"],
        }
    return stages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--task-index", required=True, type=int)
    args = parser.parse_args()
    job_dir = Path(args.job_dir)
    manifest = load(ROOT / "benchmark/architectures.json")
    condition = manifest["conditions"][args.condition]
    violations = []
    observed = {}
    evidence = {}

    for filename, expected in expected_stages(condition).items():
        matches = list(job_dir.glob(f"**/agent/{filename}"))
        if len(matches) != 1:
            violations.append(f"expected one {filename}, found {len(matches)}")
            continue
        models, errors, malformed = assistant_models(matches[0])
        observed[filename] = models
        missing = expected - set(models)
        unexpected = set(models) - expected
        if missing:
            violations.append(f"{filename}: missing model(s) {sorted(missing)}")
        if unexpected:
            violations.append(f"{filename}: unexpected model(s) {sorted(unexpected)}")
        if errors:
            violations.append(f"{filename}: provider/model errors {errors}")
        if malformed:
            violations.append(f"{filename}: {malformed} malformed JSONL line(s)")
        stderr = matches[0].with_name(filename + ".stderr")
        if not stderr.exists():
            violations.append(f"{filename}: stderr capture missing")
        elif stderr.read_text(errors="replace").strip():
            violations.append(f"{filename}: stderr capture is not empty")
    if condition["treatment"] == "advisor":
        advisor_matches = list(
            job_dir.glob("**/agent/sessions/worker/**/__advisor*.jsonl")
        )
        if len(advisor_matches) != 1:
            violations.append(
                f"expected one advisor transcript, found {len(advisor_matches)}"
            )
        else:
            models, errors, tool_calls, malformed = session_assistant_evidence(
                advisor_matches[0]
            )
            advisor_label = "worker/__advisor.jsonl"
            observed[advisor_label] = models
            expected_advisor = {condition["advisor_model"]}
            missing = expected_advisor - set(models)
            unexpected = set(models) - expected_advisor
            if missing:
                violations.append(
                    f"{advisor_label}: missing model(s) {sorted(missing)}"
                )
            if unexpected:
                violations.append(
                    f"{advisor_label}: unexpected model(s) {sorted(unexpected)}"
                )
            if errors:
                violations.append(f"{advisor_label}: provider/model errors {errors}")
            if malformed:
                violations.append(
                    f"{advisor_label}: {malformed} malformed JSONL line(s)"
                )
            allowed_advisor_tools = {"read", "grep", "glob", "advise"}
            disallowed = sorted(set(tool_calls) - allowed_advisor_tools)
            if disallowed:
                violations.append(
                    f"{advisor_label}: disallowed tool call(s) {disallowed}"
                )
            evidence["advisor_tool_calls"] = tool_calls

    spawns = list(job_dir.glob("**/agent/benchmark-spawns.jsonl"))
    if spawns:
        violations.append("implementation subagent record exists")
    contract_path = job_dir / "run-contract.json"
    if not contract_path.exists():
        violations.append("run-contract.json missing")
    else:
        contract = load(contract_path)
        if (
            contract.get("schema_version") != 4
            or contract.get("condition_id") != args.condition
        ):
            violations.append("run contract does not match v4 condition")
        current_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        evidence["git_commit"] = current_commit
        if contract.get("git_commit") != current_commit:
            violations.append("run contract git commit does not match current checkout")

    model_timeout = validate_result(job_dir, condition, violations, evidence)
    validate_finalization(job_dir, model_timeout, violations, evidence)

    collected = list(job_dir.glob("**/artifacts/model.patch"))
    expected = list(job_dir.glob("**/agent/final.patch"))
    if len(collected) != 1 or len(expected) != 1:
        violations.append(
            f"expected one collected and final patch, found {len(collected)} and {len(expected)}"
        )
    else:
        collected_hash = sha256(collected[0])
        expected_hash = sha256(expected[0])
        evidence["patch_sha256"] = {
            "collected": collected_hash,
            "final": expected_hash,
        }
        if collected_hash != expected_hash:
            violations.append("collected model patch differs from final solution patch")
    status = (
        "INVALID_HARNESS"
        if violations
        else "VALID_MODEL_TIMEOUT"
        if model_timeout
        else "VALID"
    )
    report = {
        "status": status,
        "condition_id": args.condition,
        "treatment": condition["treatment"],
        "task_index": args.task_index,
        "observed_stage_models": observed,
        "violations": violations,
        "evidence": evidence,
    }
    (job_dir / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(2 if violations else 0)


if __name__ == "__main__":
    main()
