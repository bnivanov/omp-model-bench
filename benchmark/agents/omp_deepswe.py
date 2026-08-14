from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from benchmark.agents.omp_pier import OmpLocal, _Usage
from pier.agents.installed.base import with_prompt_template
from pier.models.agent.context import AgentContext
from pier.models.agent.install import AgentInstallSpec, InstallStep
from pier.models.agent.network import NetworkAllowlist

BENCH_ROOT = Path(__file__).resolve().parents[2]

WORKER_TOOLS = ["read", "grep", "glob", "edit", "write", "bash", "lsp"]
PREWALK_TOOLS = [*WORKER_TOOLS, "todo"]
REVIEWER_TOOLS = ["read", "grep", "glob"]
TREATMENTS = {
    "solo",
    "plan_yolo",
    "prewalk",
    "advisor",
    "review",
    "plan_yolo_review",
    "prewalk_review",
}
PROMPT_SCAFFOLDS = {"none", "ultrathink"}


def _selector_with_thinking(model: str, thinking: str | None) -> str:
    leaf = model.rsplit("/", 1)[-1]
    if ":" in leaf:
        base, configured = model.rsplit(":", 1)
        if thinking and configured != thinking:
            raise ValueError(
                f"Model selector {model!r} conflicts with frozen thinking {thinking!r}"
            )
        return model
    return f"{model}:{thinking}" if thinking else model


def _canonical_selector(model: str) -> str:
    provider, leaf = model.split("/", 1)
    return f"{provider}/{leaf.rsplit(':', 1)[0]}"


class OmpDeepSWE(OmpLocal):
    """DeepSWE-specific OMP treatment harness.

    Scientific controls are Pier AgentConfig kwargs so they are recorded in
    config.json and lock.json. Infrastructure plumbing remains OMP_BENCH_* env.
    """

    def __init__(
        self,
        *args,
        treatment: str = "solo",
        worker_model: str | None = None,
        planner_model: str | None = None,
        prewalker_model: str | None = None,
        advisor_model: str | None = None,
        reviewer_model: str | None = None,
        prompt_scaffold: str = "none",
        thinking: str = "max",
        advisor_sync_backlog: int = 1,
        advisor_immune_turns: int = 3,
        repair_passes: int = 1,
        subagents: bool = False,
        **kwargs,
    ) -> None:
        model_name = kwargs.get("model_name")
        if treatment not in TREATMENTS:
            raise ValueError(
                f"Unsupported treatment {treatment!r}; expected one of {sorted(TREATMENTS)}"
            )

        if thinking != "max":
            raise ValueError(
                "This benchmark freezes every model role at thinking='max'"
            )
        if advisor_sync_backlog != 1 or advisor_immune_turns != 3:
            raise ValueError(
                "This benchmark freezes advisor_sync_backlog=1 and advisor_immune_turns=3"
            )
        resolved_worker = worker_model or model_name
        if not resolved_worker:
            raise ValueError("worker_model or Pier model_name is required")
        if model_name and worker_model and model_name != worker_model:
            raise ValueError(
                f"Pier model_name {model_name!r} must match worker_model {worker_model!r}"
            )
        if treatment in {"plan_yolo", "plan_yolo_review"} and not planner_model:
            raise ValueError(f"{treatment} requires planner_model")
        if treatment in {"prewalk", "prewalk_review"} and not prewalker_model:
            raise ValueError(f"{treatment} requires prewalker_model")
        if prompt_scaffold not in PROMPT_SCAFFOLDS:
            raise ValueError(
                f"Unsupported prompt_scaffold {prompt_scaffold!r}; "
                f"expected one of {sorted(PROMPT_SCAFFOLDS)}"
            )
        if prompt_scaffold != "none" and treatment != "solo":
            raise ValueError(
                "prompt_scaffold is frozen as a solo-only control in this experiment"
            )
        if planner_model and treatment not in {"plan_yolo", "plan_yolo_review"}:
            raise ValueError(f"planner_model is not valid for treatment {treatment!r}")
        if prewalker_model and treatment not in {"prewalk", "prewalk_review"}:
            raise ValueError(
                f"prewalker_model is not valid for treatment {treatment!r}"
            )
        if advisor_model and treatment != "advisor":
            raise ValueError(f"advisor_model is not valid for treatment {treatment!r}")
        if reviewer_model and treatment not in {
            "review",
            "plan_yolo_review",
            "prewalk_review",
        }:
            raise ValueError(f"reviewer_model is not valid for treatment {treatment!r}")
        if treatment == "advisor" and not advisor_model:
            raise ValueError("advisor treatment requires advisor_model")
        if (
            treatment in {"review", "plan_yolo_review", "prewalk_review"}
            and not reviewer_model
        ):
            raise ValueError(f"{treatment} requires reviewer_model")
        if repair_passes != 1:
            raise ValueError("This benchmark freezes review to exactly one repair pass")
        if subagents:
            raise ValueError("This benchmark forbids implementation subagents")

        self.treatment = treatment
        self.worker_model = _canonical_selector(resolved_worker)
        self.planner_model = (
            _canonical_selector(planner_model) if planner_model else None
        )
        self.prewalker_model = (
            _canonical_selector(prewalker_model) if prewalker_model else None
        )
        self.advisor_model = (
            _canonical_selector(advisor_model) if advisor_model else None
        )
        self.reviewer_model = (
            _canonical_selector(reviewer_model) if reviewer_model else None
        )
        self.prompt_scaffold = prompt_scaffold
        self.benchmark_thinking = thinking
        self.advisor_sync_backlog = advisor_sync_backlog
        self.advisor_immune_turns = advisor_immune_turns
        self.repair_passes = repair_passes
        self.subagents = subagents
        self._stage_records: list[dict[str, object]] = []
        self._base_commit: str | None = None
        self._base_stashes: set[str] = set()

        super().__init__(*args, **kwargs)
        self._thinking = thinking

    async def _install_benchmark_assets(self, environment):
        """Install only the spawn-cap hook; old worker profiles are retired."""
        hook_src = BENCH_ROOT / ".omp/hooks/pre/benchmark-spawn-cap.ts"
        if not hook_src.is_file():
            raise FileNotFoundError(hook_src)

        await environment.upload_file(str(hook_src), "/tmp/benchmark-spawn-cap.ts")
        await self.exec_as_agent(
            environment,
            command=(
                'mkdir -p "$HOME/.omp/agent/hooks/pre" && '
                "cp /tmp/benchmark-spawn-cap.ts "
                '"$HOME/.omp/agent/hooks/pre/benchmark-spawn-cap.ts"'
            ),
        )

    def install_spec(self):
        return AgentInstallSpec(
            agent_name=self.name(),
            version=self._version,
            steps=[InstallStep(user="root", run="mkdir -p /installed-agent")],
        )

    def network_allowlist(self):
        host = urlparse(self._gateway_url).hostname
        return NetworkAllowlist(domains=[host] if host else [])

    async def setup(self, environment):
        await environment.exec(command="mkdir -p /installed-agent", user="root")
        await self.install(environment)
        await self._install_benchmark_assets(environment)

        if self._version is None:
            command = self.get_version_command()
            if command:
                result = await environment.exec(command=command)
                if result.return_code == 0 and result.stdout:
                    self._version = self.parse_version(result.stdout)

    async def _write_config(self, environment):
        advisor_enabled = self.treatment == "advisor"
        magic_enabled = self.prompt_scaffold == "ultrathink"
        lines = [
            "web_search:",
            "  enabled: false",
            "magicKeywords:",
            f"  enabled: {'true' if magic_enabled else 'false'}",
            f"  ultrathink: {'true' if magic_enabled else 'false'}",
            "  orchestrate: false",
            "  workflow: false",
            "advisor:",
            f"  enabled: {'true' if advisor_enabled else 'false'}",
            f"  syncBacklog: {self.advisor_sync_backlog}",
            f"  immuneTurns: {self.advisor_immune_turns}",
            "  subagents: false",
            "retry:",
            "  fallbackChains:",
            "    default: []",
            "task:",
            "  batch: false",
            "  maxConcurrency: 1",
            "  maxRecursionDepth: 1",
            "  enableEffort: false",
        ]

        if self.advisor_model:
            advisor_selector = _selector_with_thinking(
                self.advisor_model, self.benchmark_thinking
            )
            lines = [
                "modelRoles:",
                f"  advisor: {json.dumps(advisor_selector)}",
                *lines,
            ]

        content = "\n".join(lines) + "\n"
        await self.exec_as_agent(
            environment,
            command=(
                'mkdir -p "$HOME/.omp/agent" && '
                "cat > \"$HOME/.omp/agent/config.yml\" <<'OMP_CONFIG_EOF'\n"
                + content
                + "OMP_CONFIG_EOF"
            ),
        )

    def _entry_instruction(self, instruction: str) -> str:
        """Apply a turn-scoped OMP prompt scaffold only to the initial task turn."""
        if self.prompt_scaffold == "ultrathink":
            return "ultrathink\n\n" + instruction
        return instruction

    async def _run_stage(
        self,
        environment,
        *,
        role: str,
        label: str,
        instruction: str,
        model: str,
        tools: list[str],
        extra_args: list[str] | None = None,
        kind: str = "normal",
    ) -> None:
        output_filename = f"{label}.jsonl"
        session_dir = f"/logs/agent/sessions/{label}"

        record = {
            "role": role,
            "label": label,
            "kind": kind,
            "output_filename": output_filename,
            "stderr_filename": f"{output_filename}.stderr",
            "session_dir": f"sessions/{label}",
            "model": _canonical_selector(model),
            "expected_models": (
                [self.planner_model, self.worker_model]
                if kind == "plan_yolo_worker"
                else [self.prewalker_model, self.worker_model]
                if kind == "prewalk_worker"
                else [self.worker_model, self.advisor_model]
                if self.treatment == "advisor" and role == "worker"
                else [_canonical_selector(model)]
            ),
            "return_code": None,
        }
        # Register the stage before launching OMP so Pier's post-run hook can
        # attribute partial usage when the outer task deadline cancels this await.
        self._stage_records.append(record)
        return_code = await self._execute_omp(
            instruction,
            environment,
            model_name=model,
            output_filename=output_filename,
            extra_args=extra_args,
            tools=tools,
            session_dir=session_dir,
            no_session=False,
            run_env_overrides={"OMP_BENCH_MAX_SPAWNS": "0"},
        )
        record["return_code"] = return_code
        if return_code != 0:
            raise RuntimeError(
                f"OMP stage {label!r} failed with exit code {return_code}; "
                f"see {output_filename}.stderr"
            )

    def _advisor_usage_by_model(self) -> dict[str, _Usage]:
        usage_by_model: dict[str, _Usage] = {}
        advisor_root = self.logs_dir / "sessions" / "worker"
        if not advisor_root.exists():
            return usage_by_model

        for path in advisor_root.rglob("__advisor*.jsonl"):
            with path.open(errors="replace") as fh:
                for line in fh:
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue
                    if entry.get("type") != "message":
                        continue
                    message = entry.get("message")
                    if (
                        not isinstance(message, dict)
                        or message.get("role") != "assistant"
                    ):
                        continue
                    provider, model = message.get("provider"), message.get("model")
                    if not isinstance(provider, str) or not isinstance(model, str):
                        key = "unknown"
                    else:
                        key = _canonical_selector(f"{provider}/{model}")
                    usage_by_model.setdefault(key, _Usage()).add(message.get("usage"))
        return usage_by_model

    async def _workspace_patch(self, environment) -> str:
        if not self._base_commit:
            raise RuntimeError("base commit was not captured")
        result = await self.exec_as_agent(
            environment,
            command=(
                "tmp=$(mktemp -u); "
                "trap 'rm -f \"$tmp\"' EXIT; "
                f'GIT_INDEX_FILE="$tmp" git read-tree {self._base_commit}; '
                'GIT_INDEX_FILE="$tmp" git add -A; '
                f'GIT_INDEX_FILE="$tmp" git diff --cached --no-ext-diff --binary '
                f"{self._base_commit} -- ."
            ),
        )
        if result.return_code != 0:
            raise RuntimeError("Could not capture complete candidate patch")
        return result.stdout or ""

    async def _run_review_and_repair(self, instruction: str, environment) -> None:
        if not self.reviewer_model:
            raise RuntimeError("reviewer_model is required")

        patch = await self._workspace_patch(environment)
        reviewer_prompt = (
            "INDEPENDENT FINAL REVIEW\n"
            "You are a read-only reviewer. Do not implement or edit anything. "
            "Review the candidate solution against the ORIGINAL TASK. "
            "Look for correctness bugs, missed edge cases, regressions, aliasing/state "
            "problems, and incomplete behavior. Return concise actionable findings. "
            "If you find no material issue, output exactly NO_CHANGES_NEEDED.\n\n"
            "ORIGINAL TASK\n"
            + instruction
            + "\n\nCANDIDATE PATCH\n"
            + (patch if patch.strip() else "(no diff captured)")
        )
        before_review = await self._workspace_patch(environment)

        await self._run_stage(
            environment,
            role="reviewer",
            label="reviewer",
            instruction=reviewer_prompt,
            model=self.reviewer_model,
            tools=REVIEWER_TOOLS,
        )
        after_review = await self._workspace_patch(environment)
        if after_review != before_review:
            raise RuntimeError(
                "Reviewer mutated the workspace; run is infrastructure-invalid"
            )

        findings = self._final_assistant_text(self.logs_dir / "reviewer.jsonl")
        if not findings.strip():
            findings = "Reviewer produced no textual findings."

        repair_prompt = (
            "ONE REPAIR PASS\n"
            "This is the only post-review repair pass. Inspect the CURRENT workspace. "
            "Treat the independent review as advice, not ground truth: verify each "
            "finding yourself, make only necessary corrections, and validate the "
            "solution. Do not ask for another reviewer.\n\n"
            "ORIGINAL TASK\n" + instruction + "\n\nREVIEW FINDINGS\n" + findings
        )

        await self._run_stage(
            environment,
            role="repair",
            label="repair",
            instruction=repair_prompt,
            model=self.worker_model,
            tools=WORKER_TOOLS,
        )

    async def _recover_cancelled_stash(self, environment) -> str | None:
        state = await self.exec_as_agent(
            environment,
            command=(
                "git diff --quiet; unstaged=$?; "
                "git diff --cached --quiet; staged=$?; "
                "printf 'tracked_dirty=%s\\n' \"$((unstaged != 0 || staged != 0))\"; "
                "git stash list --format='%H'"
            ),
        )
        if state.return_code != 0 or not state.stdout.strip():
            raise RuntimeError("Could not inspect deadline workspace state")
        lines = state.stdout.strip().splitlines()
        tracked_dirty = lines[0] == "tracked_dirty=1"
        base_stashes = getattr(self, "_base_stashes", set())
        new_stashes = [ref for ref in lines[1:] if ref not in base_stashes]
        if not new_stashes:
            return None
        if tracked_dirty or len(new_stashes) != 1:
            raise RuntimeError(
                "Deadline workspace has ambiguous tracked changes and/or stashes"
            )
        recovered = new_stashes[0]
        applied = await self.exec_as_agent(
            environment,
            command=f"git stash apply --index {recovered}",
        )
        if applied.return_code != 0:
            raise RuntimeError("Could not restore the deadline candidate from stash")
        return recovered

    async def _capture_final_solution(
        self, environment, *, recover_cancelled_stash: bool = False
    ) -> None:
        if not self._base_commit:
            raise RuntimeError("base commit was not captured")
        recovered_stash = (
            await self._recover_cancelled_stash(environment)
            if recover_cancelled_stash
            else None
        )
        final_commit = await self.exec_as_agent(
            environment,
            command=(
                "git add -A && "
                "if ! git diff --cached --quiet; then "
                "git -c user.name='OMP Benchmark' "
                "-c user.email='omp-benchmark@localhost' "
                "commit -m 'OMP benchmark solution'; "
                "fi; "
                "git rev-parse HEAD"
            ),
        )
        if final_commit.return_code != 0 or not final_commit.stdout.strip():
            raise RuntimeError("Could not capture final solution commit")
        final_head = final_commit.stdout.strip().splitlines()[-1]
        final_patch = await self.exec_as_agent(
            environment,
            command=(
                "mkdir -p /logs/agent; "
                f"git diff --binary {self._base_commit} {final_head} -- . "
                "> /logs/agent/final.patch && "
                "cat > /logs/agent/finalization.json <<'OMP_FINALIZATION_EOF'\n"
                + json.dumps(
                    {
                        "base_commit": self._base_commit,
                        "final_commit": final_head,
                        "recovered_cancelled_stash": recovered_stash,
                    },
                    sort_keys=True,
                )
                + "\nOMP_FINALIZATION_EOF"
            ),
        )
        if final_patch.return_code != 0:
            raise RuntimeError("Could not capture final solution patch")

    async def _run_treatment(self, instruction, environment) -> None:
        base = await self.exec_as_agent(
            environment,
            command="git rev-parse HEAD; git stash list --format='%H'",
        )
        if base.return_code != 0:
            raise RuntimeError("Could not inspect DeepSWE base repository state")
        base_lines = base.stdout.strip().splitlines()
        self._base_commit = base_lines[0] if base_lines else None
        self._base_stashes = set(base_lines[1:])

        entry_instruction = self._entry_instruction(instruction)

        if self.treatment == "solo":
            await self._run_stage(
                environment,
                role="worker",
                label="worker",
                instruction=entry_instruction,
                model=self.worker_model,
                tools=WORKER_TOOLS,
            )

        elif self.treatment == "plan_yolo":
            assert self.planner_model is not None
            await self._run_stage(
                environment,
                role="plan_yolo_worker",
                label="plan_yolo_worker",
                instruction=entry_instruction,
                model=self.planner_model,
                tools=WORKER_TOOLS,
                extra_args=[
                    "--plan-yolo",
                    "--plan-yolo-into",
                    _selector_with_thinking(self.worker_model, self.benchmark_thinking),
                ],
                kind="plan_yolo_worker",
            )

        elif self.treatment == "prewalk":
            assert self.prewalker_model is not None
            await self._run_stage(
                environment,
                role="prewalk_worker",
                label="prewalk_worker",
                instruction=entry_instruction,
                model=self.prewalker_model,
                tools=PREWALK_TOOLS,
                extra_args=[
                    "--prewalk",
                    "--prewalk-into",
                    _selector_with_thinking(self.worker_model, self.benchmark_thinking),
                ],
                kind="prewalk_worker",
            )

        elif self.treatment == "advisor":
            await self._run_stage(
                environment,
                role="worker",
                label="worker",
                instruction=entry_instruction,
                model=self.worker_model,
                tools=WORKER_TOOLS,
                extra_args=["--advisor"],
            )

        elif self.treatment == "review":
            await self._run_stage(
                environment,
                role="worker",
                label="worker",
                instruction=entry_instruction,
                model=self.worker_model,
                tools=WORKER_TOOLS,
            )
            await self._run_review_and_repair(instruction, environment)

        elif self.treatment == "plan_yolo_review":
            assert self.planner_model is not None
            await self._run_stage(
                environment,
                role="plan_yolo_worker",
                label="plan_yolo_worker",
                instruction=entry_instruction,
                model=self.planner_model,
                tools=WORKER_TOOLS,
                extra_args=[
                    "--plan-yolo",
                    "--plan-yolo-into",
                    _selector_with_thinking(self.worker_model, self.benchmark_thinking),
                ],
                kind="plan_yolo_worker",
            )
            await self._run_review_and_repair(instruction, environment)

        elif self.treatment == "prewalk_review":
            assert self.prewalker_model is not None
            await self._run_stage(
                environment,
                role="prewalk_worker",
                label="prewalk_worker",
                instruction=entry_instruction,
                model=self.prewalker_model,
                tools=PREWALK_TOOLS,
                extra_args=[
                    "--prewalk",
                    "--prewalk-into",
                    _selector_with_thinking(self.worker_model, self.benchmark_thinking),
                ],
                kind="prewalk_worker",
            )
            await self._run_review_and_repair(instruction, environment)

        await self._capture_final_solution(environment)

    @with_prompt_template
    async def run(self, instruction, environment, context):
        try:
            await self._run_treatment(instruction, environment)
        except BaseException:
            if self._base_commit and getattr(
                self, "_workspace_stable_on_failure", True
            ):
                try:
                    await self._capture_final_solution(
                        environment, recover_cancelled_stash=True
                    )
                except BaseException:
                    # Preserve the original timeout/stage failure. The validator will
                    # independently flag a missing or mismatched final patch.
                    pass
            raise

    def populate_context_post_run(self, context: AgentContext) -> None:
        if not self._stage_records:
            return super().populate_context_post_run(context)

        stage_usage: dict[str, _Usage] = {}
        total = _Usage()
        unclassified = _Usage()

        advisor_by_model = (
            self._advisor_usage_by_model() if self.treatment == "advisor" else {}
        )

        for record in self._stage_records:
            output = self.logs_dir / str(record["output_filename"])
            observed_models = set(self._usage_by_model(output))
            if self.treatment == "advisor" and record["role"] == "worker":
                observed_models.update(advisor_by_model)
            expected_models = {
                model for model in record["expected_models"] if isinstance(model, str)
            }
            if not expected_models.issubset(observed_models):
                missing = sorted(expected_models - observed_models)
                raise RuntimeError(
                    f"OMP stage {record['label']!r} missed expected model handoff(s): {missing}"
                )
            kind = str(record["kind"])

            if kind in {"plan_yolo_worker", "prewalk_worker"}:
                by_model = self._usage_by_model(output)
                source_role = "planner" if kind == "plan_yolo_worker" else "prewalker"
                source_model = (
                    self.planner_model
                    if kind == "plan_yolo_worker"
                    else self.prewalker_model
                )
                source_usage = (
                    by_model.pop(source_model, _Usage()) if source_model else _Usage()
                )
                worker_usage = by_model.pop(self.worker_model, _Usage())

                stage_usage.setdefault(source_role, _Usage()).merge(source_usage)
                stage_usage.setdefault("worker", _Usage()).merge(worker_usage)
                total.merge(source_usage)
                total.merge(worker_usage)

                for usage in by_model.values():
                    unclassified.merge(usage)
                    total.merge(usage)
            else:
                role = str(record["role"])
                if self.treatment == "advisor" and role == "worker":
                    by_model = self._usage_by_model(output)
                    usage = by_model.pop(self.worker_model, _Usage())
                    for extra in by_model.values():
                        unclassified.merge(extra)
                else:
                    usage = _Usage()
                    self._sum_main(output, usage)
                stage_usage.setdefault(role, _Usage()).merge(usage)
                total.merge(usage)

        if self.treatment == "advisor":
            advisor_usage = advisor_by_model.pop(self.advisor_model, _Usage())
            stage_usage["advisor"] = advisor_usage
            total.merge(advisor_usage)
            for extra in advisor_by_model.values():
                unclassified.merge(extra)
                total.merge(extra)
            if advisor_usage.empty():
                raise RuntimeError("Advisor treatment recorded no advisor usage")

        context.n_input_tokens = total.in_tok + total.cache_read
        context.n_output_tokens = total.out_tok
        context.n_cache_tokens = total.cache_read
        context.cost_usd = total.cost if total.cost > 0 else None

        metadata = {
            **(context.metadata or {}),
            "benchmark_schema_version": 4,
            "treatment": self.treatment,
            "worker_model": self.worker_model,
            "planner_model": self.planner_model,
            "prewalker_model": self.prewalker_model,
            "advisor_model": self.advisor_model,
            "reviewer_model": self.reviewer_model,
            "prompt_scaffold": self.prompt_scaffold,
            "thinking": self.benchmark_thinking,
            "advisor_sync_backlog": self.advisor_sync_backlog,
            "advisor_immune_turns": self.advisor_immune_turns,
            "repair_passes": self.repair_passes,
            "subagents": False,
            "stages": {role: usage.as_dict() for role, usage in stage_usage.items()},
            "cache_write_tokens": total.cache_write,
        }
        if not unclassified.empty():
            raise RuntimeError(
                "Stage usage contained unclassified provider/model events; "
                "the run is infrastructure-invalid"
            )
        context.metadata = metadata


class OmpInstallSmoke(OmpDeepSWE):
    async def run(self, instruction, environment, context):
        await self.exec_as_agent(
            environment,
            command=f"{self._cli} --version > /logs/agent/omp-version.txt 2>&1",
        )


class OmpNetworkSmoke(OmpDeepSWE):
    async def run(self, instruction, environment, context):
        await self.exec_as_agent(
            environment,
            command="""python3 - <<'PYTEST' > /logs/agent/network-smoke.txt 2>&1
import socket
import urllib.request

def tcp(host, port):
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except Exception:
        return False

try:
    with urllib.request.urlopen("http://host.docker.internal:4000/healthz", timeout=3) as r:
        gateway = r.status == 200
except Exception:
    gateway = False

external_dns = tcp("example.com", 443)
external_ip = tcp("1.1.1.1", 443)

print(f"gateway_allowed={gateway}")
print(f"external_dns_allowed={external_dns}")
print(f"external_ip_allowed={external_ip}")

if not gateway or external_dns or external_ip:
    raise SystemExit(1)

print("NETWORK_ISOLATION_OK")
PYTEST""",
        )


class OmpNetworkDiag(OmpDeepSWE):
    async def run(self, instruction, environment, context):
        await self.exec_as_agent(
            environment,
            command=r"""python3 - <<'PYTEST' > /logs/agent/network-diag.txt 2>&1
import os
import socket
import urllib.request

print("HTTP_PROXY=" + os.environ.get("HTTP_PROXY", ""))
print("HTTPS_PROXY=" + os.environ.get("HTTPS_PROXY", ""))

for host, port in [
    ("example.com", 443),
    ("host.docker.internal", 4000),
    ("pier-egress-proxy", 8080),
]:
    print(f"\nHOST {host}")
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except Exception as e:
        print("resolve_error=", repr(e))
        continue

    seen = set()
    for family, socktype, proto, canonname, sockaddr in infos:
        key = (family, sockaddr)
        if key in seen:
            continue
        seen.add(key)
        label = "IPv6" if family == socket.AF_INET6 else "IPv4"
        print(f"{label} {sockaddr}")
        s = socket.socket(family, socket.SOCK_STREAM)
        s.settimeout(3)
        try:
            s.connect(sockaddr)
            print("  direct_connect=SUCCESS")
        except Exception as e:
            print("  direct_connect=BLOCKED", type(e).__name__)
        finally:
            s.close()

print("\nHTTP VIA PIER PROXY")
try:
    urllib.request.urlopen("https://example.com", timeout=5)
    print("proxy_external=UNEXPECTED_SUCCESS")
except Exception as e:
    print("proxy_external=BLOCKED", type(e).__name__)

print("\nHTTP WITHOUT PROXY")
try:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    opener.open("https://example.com", timeout=5)
    print("no_proxy_external=UNEXPECTED_SUCCESS")
except Exception as e:
    print("no_proxy_external=BLOCKED", type(e).__name__)
PYTEST""",
        )


class OmpGatewaySmoke(OmpDeepSWE):
    async def run(self, instruction, environment, context):
        await self.exec_as_agent(
            environment,
            command=r"""python3 - <<'PYTEST' > /logs/agent/gateway-smoke.txt 2>&1
import urllib.request

url = "http://host.docker.internal:4000/healthz"
try:
    with urllib.request.urlopen(url, timeout=5) as r:
        body = r.read().decode("utf-8", errors="replace")
        print("status=", r.status)
        print("body=", body)
        if r.status != 200:
            raise SystemExit(1)
except Exception as e:
    print("gateway_error=", repr(e))
    raise

print("ISOLATED_GATEWAY_OK")
PYTEST""",
        )


class OmpIsolatedModelSmoke(OmpDeepSWE):
    async def run(self, instruction, environment, context):
        await OmpLocal.run(
            self, "Reply exactly ISOLATED_MODEL_OK", environment, context
        )
