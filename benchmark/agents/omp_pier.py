"""Pier agent that runs the LOCAL oh-my-pi (`omp`) build inside task containers.

This is the frozen OMP 17.2.15 benchmark adapter. Infrastructure settings
still come from OMP_BENCH_* environment variables, while experiment treatment
settings belong in the Pier AgentConfig kwargs handled by OmpDeepSWE.

Auth never enters the task container: models.yml routes configured providers to
the host auth gateway (normally http://host.docker.internal:4000).
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import override

from pier.agents.installed.base import BaseInstalledAgent, with_prompt_template
from pier.environments.base import BaseEnvironment
from pier.models.agent.context import AgentContext


def _patch_harbor_cleanup_cancellation() -> None:
    """Legacy cleanup patch retained for source lineage; disabled under Pier."""
    from pier.trial.trial import Trial

    if getattr(Trial, "_omp_cleanup_cancellation_patch", False):
        return

    async def _stop_agent_environment(self) -> None:
        if self._is_agent_environment_stopped:
            return

        stop_task = asyncio.create_task(
            self.agent_environment.stop(delete=self.config.environment.delete)
        )
        cancellation_logged = False
        while not stop_task.done():
            try:
                await asyncio.shield(stop_task)
            except asyncio.CancelledError:
                if not cancellation_logged:
                    self.logger.debug(
                        f"Cleanup cancellation delayed for {self.config.trial_name}; "
                        "waiting for agent environment stop to finish"
                    )
                    cancellation_logged = True
            except Exception:
                break
        try:
            await stop_task
            self._is_agent_environment_stopped = True
        except asyncio.CancelledError:
            self._is_agent_environment_stopped = True
            self.logger.debug(
                f"Agent environment stop was cancelled for {self.config.trial_name}"
            )
        except Exception as exc:
            self._is_agent_environment_stopped = True
            self.logger.debug(
                "Warning: Agent environment cleanup failed for "
                f"{self.config.trial_name}: {exc}"
            )
            self._record_exception(exc)

    Trial._stop_agent_environment = _stop_agent_environment
    Trial._omp_cleanup_cancellation_patch = True


def _patch_apple_container_dns() -> None:
    """Inject an explicit resolver into Apple Container runs when requested."""
    dns = os.environ.get("OMP_BENCH_CONTAINER_DNS")
    if not dns:
        return
    from pier.environments.apple_container import AppleContainerEnvironment

    if getattr(AppleContainerEnvironment, "_omp_dns_patch", False):
        return
    original = AppleContainerEnvironment._run_container_command

    async def _run_with_dns(self, args, *pargs, **kwargs):
        if args and args[0] == "run":
            args = ["run", "--dns", dns, *args[1:]]
        return await original(self, args, *pargs, **kwargs)

    AppleContainerEnvironment._run_container_command = _run_with_dns
    AppleContainerEnvironment._omp_dns_patch = True


# Harbor-only cleanup patch disabled under Pier.
# _patch_harbor_cleanup_cancellation()
_patch_apple_container_dns()

_TARBALL_DST = "/tmp/omp-local.tgz"
_MODELS_DST = "/tmp/omp-models.yml"
_CONFIG_DST = "/tmp/omp-config.yml"
_OUTPUT_FILENAME = "omp.txt"

_PROVIDER_KEYS: dict[str, list[str]] = {
    "amazon-bedrock": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"],
    "anthropic": ["ANTHROPIC_API_KEY", "ANTHROPIC_OAUTH_TOKEN"],
    "github-copilot": ["GITHUB_TOKEN"],
    "google": [
        "GEMINI_API_KEY",
        "GOOGLE_GENERATIVE_AI_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "GOOGLE_GENAI_USE_VERTEXAI",
    ],
    "groq": ["GROQ_API_KEY"],
    "huggingface": ["HF_TOKEN"],
    "mistral": ["MISTRAL_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
    "xai": ["XAI_API_KEY"],
}


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return value if value is not None and value != "" else default


def _truthy(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def _loads(line: str) -> dict | None:
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        value = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _selector(provider: object, model: object) -> str | None:
    if not isinstance(provider, str) or not isinstance(model, str):
        return None
    return f"{provider}/{model}"


@dataclass
class _Usage:
    """Running sum of token/cost usage across assistant turns."""

    in_tok: int = 0
    out_tok: int = 0
    cache_read: int = 0
    cache_write: int = 0
    cost: float = 0.0

    def add(self, usage: object) -> None:
        if not isinstance(usage, dict):
            return
        self.in_tok += int(usage.get("input", 0) or 0)
        self.out_tok += int(usage.get("output", 0) or 0)
        self.cache_read += int(usage.get("cacheRead", 0) or 0)
        self.cache_write += int(usage.get("cacheWrite", 0) or 0)
        cost = usage.get("cost")
        if isinstance(cost, dict):
            self.cost += float(cost.get("total", 0.0) or 0.0)

    def merge(self, other: "_Usage") -> None:
        self.in_tok += other.in_tok
        self.out_tok += other.out_tok
        self.cache_read += other.cache_read
        self.cache_write += other.cache_write
        self.cost += other.cost

    def empty(self) -> bool:
        return (
            self.in_tok == 0
            and self.out_tok == 0
            and self.cache_read == 0
            and self.cache_write == 0
            and self.cost == 0.0
        )

    def as_dict(self) -> dict[str, int | float]:
        return {
            "input_tokens": self.in_tok,
            "cache_read_tokens": self.cache_read,
            "cache_write_tokens": self.cache_write,
            "output_tokens": self.out_tok,
            "total_tokens": self.in_tok + self.cache_read + self.cache_write + self.out_tok,
            "cost_usd": self.cost,
        }


class OmpLocal(BaseInstalledAgent):
    CLI_FLAGS = []  # type: ignore[assignment]
    ENV_VARS = []  # type: ignore[assignment]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._install_mode = _env("OMP_BENCH_INSTALL", "source")
        self._tarball = _env("OMP_BENCH_TARBALL")
        self._pkg_version = _env("OMP_BENCH_VERSION", "latest")
        self._models_yaml_path = _env("OMP_BENCH_MODELS_YAML")
        self._gateway_url = _env(
            "OMP_BENCH_GATEWAY_URL", "http://host.docker.internal:4000"
        )
        self._gateway_token = _env("OMP_BENCH_GATEWAY_TOKEN", "no-auth-dummy")
        self._gateway_providers = [
            p.strip()
            for p in _env(
                "OMP_BENCH_GATEWAY_PROVIDERS", "anthropic,openai-codex"
            ).split(",")
            if p.strip()
        ]
        self._thinking = _env("OMP_BENCH_THINKING")
        self._auto_approve = _truthy(_env("OMP_BENCH_AUTO_APPROVE", "1"))
        self._agent_args = self._parse_agent_args()
        self._bun_version = _env("OMP_BENCH_BUN_VERSION", "1.3.14")
        self._gateway_on = _env("OMP_BENCH_GATEWAY", "1") != "0"
        self._web_search = _truthy(_env("OMP_BENCH_WEB_SEARCH", "0"))
        self._forward_env = self._parse_forward_env()
        self._source_dir = _env("OMP_BENCH_SOURCE_DIR", "/opt/omp/src")
        self._source_bun = _env("OMP_BENCH_SOURCE_BUN", "/opt/omp/bin/bun")
        self._source_arch = _env("OMP_BENCH_SOURCE_ARCH")
        self._home = "/root"
        self._bun = "/root/.bun/bin/bun"
        self._cli = "/root/.omp-bench/app/dist/cli.js"
        self._binary_arm64 = _env("OMP_BENCH_BINARY_ARM64")
        self._binary_x64 = _env("OMP_BENCH_BINARY_X64")
        self._binary = bool(self._binary_arm64 or self._binary_x64)
        self._workspace_stable_on_failure = True

    @staticmethod
    @override
    def name() -> str:
        return "omp"

    @override
    def version(self) -> str | None:
        return self._version

    @override
    def get_version_command(self) -> str | None:
        if self._binary:
            return f"{shlex.quote(self._cli)} --version"
        return self._wrap(f"{shlex.quote(self._bun)} {shlex.quote(self._cli)} --version")

    @override
    def parse_version(self, stdout: str) -> str:
        return stdout.strip().splitlines()[-1].strip() if stdout.strip() else "local"

    def _wrap(self, command: str) -> str:
        bun_dir = os.path.dirname(self._bun)
        return (
            f"export BUN_INSTALL={shlex.quote(self._home + '/.bun')}; "
            f'export PATH="{bun_dir}:$PATH"; '
            f"{command}"
        )

    @override
    async def install(self, environment: BaseEnvironment) -> None:
        home = (await self.exec_as_agent(environment, command='printf %s "$HOME"')).stdout
        self._home = (home or "/root").strip() or "/root"

        if self._binary:
            await self._install_binary(environment)
        elif self._install_mode == "source":
            self._cli = await self._install_source(environment)
        else:
            await self.exec_as_root(
                environment,
                command=(
                    "set -e; "
                    "if command -v apt-get >/dev/null 2>&1; then "
                    "  apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y curl unzip ca-certificates tar; "
                    "elif command -v apk >/dev/null 2>&1; then "
                    "  echo 'ERROR: Alpine/musl base image; @oh-my-pi/pi-natives ships no musl prebuilt' >&2; exit 3; "
                    "elif command -v dnf >/dev/null 2>&1; then dnf install -y curl unzip tar; "
                    "elif command -v yum >/dev/null 2>&1; then yum install -y curl unzip tar; "
                    "fi"
                ),
            )
            await self.exec_as_agent(
                environment,
                command=(
                    "set -e; "
                    f"export BUN_INSTALL={shlex.quote(self._home + '/.bun')}; "
                    f'curl -fsSL https://bun.sh/install | bash -s "bun-v{self._bun_version}"; '
                    f"{shlex.quote(self._home + '/.bun/bin/bun')} --version"
                ),
            )
            self._bun = f"{self._home}/.bun/bin/bun"
            if self._install_mode == "published":
                self._cli = await self._install_published(environment)
            else:
                self._cli = await self._install_local(environment)

        if self._gateway_on:
            await self._write_models_yaml(environment)
        await self._write_config(environment)

    async def _install_source(self, environment: BaseEnvironment) -> str:
        arch = (await self.exec_as_agent(environment, command="uname -m")).stdout.strip()
        norm = {"aarch64": "arm64", "arm64": "arm64", "x86_64": "x64", "amd64": "x64"}.get(arch)
        if self._source_arch and norm != self._source_arch:
            raise RuntimeError(
                f"source mode: container arch {arch!r} != mounted deps tree arch "
                f"({self._source_arch}); use --binary for emulated-arch tasks"
            )
        self._bun = self._source_bun
        cli = f"{self._source_dir}/packages/coding-agent/src/cli.ts"
        q = shlex.quote
        await self.exec_as_agent(
            environment,
            command=(
                "set -e; "
                f"test -x {q(self._source_bun)} || {{ echo 'omp source mode: bun mount missing' >&2; exit 5; }}; "
                f"test -f {q(cli)} || {{ echo 'omp source mode: repo mount missing' >&2; exit 5; }}; "
                f"test -d {q(self._source_dir + '/node_modules/@oh-my-pi')} || "
                "{ echo 'omp source mode: linux deps mount missing' >&2; exit 5; }; "
                f"{q(self._source_bun)} --version"
            ),
        )
        return cli

    async def _install_local(self, environment: BaseEnvironment) -> str:
        if not self._tarball:
            raise RuntimeError("OMP_BENCH_INSTALL=local requires OMP_BENCH_TARBALL (host tarball path)")
        await environment.upload_file(self._tarball, _TARBALL_DST)
        app = f"{self._home}/.omp-bench/app"
        await self.exec_as_agent(
            environment,
            command=self._wrap(
                "set -e; "
                f"mkdir -p {shlex.quote(app)}; "
                f"tar xzf {_TARBALL_DST} -C {shlex.quote(app)} --strip-components=1; "
                f"cd {shlex.quote(app)}; "
                "bun install --production --omit=optional; "
                "arch=$(uname -m); "
                'case "$arch" in aarch64|arm64) na=arm64 ;; x86_64|amd64) na=x64 ;; '
                '*) echo "unsupported arch $arch" >&2; exit 4 ;; esac; '
                'ver=$(bun -e "process.stdout.write(require(\\"./package.json\\").version)"); '
                'echo "pinning native @oh-my-pi/pi-natives-linux-$na@$ver"; '
                'bun add --production "@oh-my-pi/pi-natives-linux-$na@$ver"'
            ),
            timeout_sec=900,
        )
        return f"{app}/dist/cli.js"

    async def _install_binary(self, environment: BaseEnvironment) -> str:
        arch = (await self.exec_as_agent(environment, command="uname -m")).stdout.strip()
        if arch in ("aarch64", "arm64"):
            hostbin = self._binary_arm64
        elif arch in ("x86_64", "amd64"):
            hostbin = self._binary_x64
        else:
            raise RuntimeError(f"binary mode: unsupported container arch {arch!r}")
        if not hostbin:
            raise RuntimeError(f"binary mode: no omp binary provided for container arch {arch}")
        app_dir = f"{self._home}/.omp-bench"
        dst = f"{app_dir}/omp"
        staging = "/tmp/omp-bin"
        await self.exec_as_agent(environment, command=f"mkdir -p {shlex.quote(app_dir)}")
        await environment.upload_file(hostbin, staging)
        await self.exec_as_agent(
            environment,
            command=f"cp {shlex.quote(staging)} {shlex.quote(dst)} && chmod +x {shlex.quote(dst)}",
        )
        self._cli = dst
        return dst

    async def _install_published(self, environment: BaseEnvironment) -> str:
        app = f"{self._home}/.omp-bench/app"
        spec = f"@oh-my-pi/pi-coding-agent@{self._pkg_version}"
        await self.exec_as_agent(
            environment,
            command=self._wrap(
                "set -e; "
                f"mkdir -p {shlex.quote(app)}; cd {shlex.quote(app)}; "
                'printf "{}" > package.json; '
                f"bun add {shlex.quote(spec)}"
            ),
            timeout_sec=900,
        )
        return f"{app}/node_modules/@oh-my-pi/pi-coding-agent/dist/cli.js"

    async def _write_models_yaml(self, environment: BaseEnvironment) -> None:
        if self._models_yaml_path and os.path.isfile(self._models_yaml_path):
            await environment.upload_file(self._models_yaml_path, _MODELS_DST)
            staged = _MODELS_DST
        else:
            content = self._generate_models_yaml()
            staged = _MODELS_DST
            heredoc = f"cat > {_MODELS_DST} <<'OMP_MODELS_EOF'\n{content}\nOMP_MODELS_EOF"
            await self.exec_as_agent(environment, command=heredoc)
        await self.exec_as_agent(
            environment,
            command=(f'mkdir -p "$HOME/.omp/agent"; cp {shlex.quote(staged)} "$HOME/.omp/agent/models.yml"'),
        )

    def _generate_models_yaml(self) -> str:
        lines = ["# Generated by benchmark adapter — routes auth via host gateway.", "providers:"]
        for provider in self._gateway_providers:
            lines += [
                f"  {provider}:",
                f"    baseUrl: {self._gateway_url}",
                "    auth: oauth",
                "    transport: pi-native",
                f"    apiKey: {self._gateway_token}",
            ]
        return "\n".join(lines)

    async def _write_config(self, environment: BaseEnvironment) -> None:
        lines = ["# Generated by benchmark adapter.", "web_search:", f"  enabled: {'true' if self._web_search else 'false'}"]
        content = "\n".join(lines)
        heredoc = f"cat > {_CONFIG_DST} <<'OMP_CONFIG_EOF'\n{content}\nOMP_CONFIG_EOF"
        await self.exec_as_agent(environment, command=heredoc)
        await self.exec_as_agent(
            environment,
            command=(f'mkdir -p "$HOME/.omp/agent"; cp {shlex.quote(_CONFIG_DST)} "$HOME/.omp/agent/config.yml"'),
        )

    @staticmethod
    def _parse_forward_env() -> dict[str, str]:
        raw = _env("OMP_BENCH_FORWARD_ENV")
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {str(key): str(value) for key, value in parsed.items()}

    @staticmethod
    def _parse_agent_args() -> list[str]:
        raw = _env("OMP_BENCH_AGENT_ARGS")
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item) for item in parsed]

    def _collect_provider_keys(self, provider: str) -> dict[str, str]:
        env: dict[str, str] = {}
        for key in _PROVIDER_KEYS.get(provider, []):
            value = os.environ.get(key)
            if value:
                env[key] = value
        return env

    async def _execute_omp(
        self,
        instruction: str,
        environment: BaseEnvironment,
        *,
        model_name: str | None = None,
        output_filename: str = _OUTPUT_FILENAME,
        extra_args: list[str] | None = None,
        tools: list[str] | None = None,
        session_dir: str | None = None,
        no_session: bool = True,
        run_env_overrides: dict[str, str] | None = None,
    ) -> int:
        """Run one headless OMP process with explicit stage controls."""
        selected = model_name or self.model_name
        if not selected or "/" not in selected:
            raise ValueError("model must be 'provider/model' (e.g. anthropic/claude-sonnet-4-6)")
        provider, model = selected.split("/", 1)
        q = shlex.quote

        if self._binary:
            parts = [q(self._cli)]
        else:
            parts = [q(self._bun), q(self._cli)]

        parts += ["--print", "--mode json", f"--provider {q(provider)}", f"--model {q(model)}"]

        if session_dir:
            await self.exec_as_agent(environment, command=f"mkdir -p {q(session_dir)}")
            parts.append(f"--session-dir {q(session_dir)}")
        elif no_session:
            parts.append("--no-session")

        if self._auto_approve:
            parts.append("--auto-approve")
        if self._thinking:
            parts.append(f"--thinking {q(self._thinking)}")
        if tools is not None:
            parts.append(f"--tools {q(','.join(tools))}")

        parts.extend(q(arg) for arg in self._agent_args)
        parts.extend(q(arg) for arg in (extra_args or []))
        parts.append("--")
        parts.append(q(instruction))

        omp_run = (
            " ".join(parts)
            + f" > /logs/agent/{q(output_filename)}"
            + f" 2> /logs/agent/{q(output_filename + '.stderr')}"
        )
        pid_file = f"/logs/agent/.{output_filename}.pid"
        run = (
            f"setsid sh -c {q('exec ' + omp_run)} & "
            'omp_pid="$!"; '
            f"printf '%s\\n' \"$omp_pid\" > {q(pid_file)}; "
            'wait "$omp_pid"; return_code="$?"; '
            f"rm -f {q(pid_file)}; exit \"$return_code\""
        )

        run_env: dict[str, str] = {}
        if not self._gateway_on:
            run_env.update(self._collect_provider_keys(provider))
        run_env.update(self._forward_env)
        if run_env_overrides:
            run_env.update(run_env_overrides)

        try:
            result = await self.exec_as_agent(
                environment,
                command=run if self._binary else self._wrap(run),
                env=run_env or None,
            )
        except asyncio.CancelledError:
            # Cancelling `docker compose exec` does not guarantee that its
            # in-container process exits. Stop the recorded OMP process group
            # before the DeepSWE wrapper snapshots the deadline workspace.
            try:
                stop = await asyncio.shield(
                    self.exec_as_agent(
                        environment,
                        command=(
                            f"if [ -s {q(pid_file)} ]; then "
                            f"omp_pid=$(cat {q(pid_file)}); "
                            'kill -TERM -- "-$omp_pid" 2>/dev/null || true; '
                            "sleep 2; "
                            'kill -KILL -- "-$omp_pid" 2>/dev/null || true; '
                            "sleep 1; "
                            "fi; "
                            f"rm -f {q(pid_file)}"
                        ),
                    )
                )
            except BaseException:
                self._workspace_stable_on_failure = False
                raise
            if stop.return_code != 0:
                self._workspace_stable_on_failure = False
            raise
        return result.return_code

    @with_prompt_template
    @override
    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        await self._execute_omp(instruction, environment)

    @override
    def populate_context_post_run(self, context: AgentContext) -> None:
        main = _Usage()
        self._sum_main(self.logs_dir / _OUTPUT_FILENAME, main)
        if main.empty():
            return
        context.n_input_tokens = main.in_tok + main.cache_read
        context.n_output_tokens = main.out_tok
        context.n_cache_tokens = main.cache_read
        context.cost_usd = main.cost if main.cost > 0 else None
        context.metadata = {**(context.metadata or {}), "cache_write_tokens": main.cache_write}

    def _sum_main(self, path: Path, acc: "_Usage") -> None:
        if not path.exists():
            return
        with path.open(errors="replace") as fh:
            for line in fh:
                event = _loads(line)
                if not event or event.get("type") != "message_end":
                    continue
                message = event.get("message")
                if isinstance(message, dict) and message.get("role") == "assistant":
                    acc.add(message.get("usage"))

    def _usage_by_model(self, path: Path) -> dict[str, "_Usage"]:
        out: dict[str, _Usage] = {}
        if not path.exists():
            return out
        with path.open(errors="replace") as fh:
            for line in fh:
                event = _loads(line)
                if not event or event.get("type") != "message_end":
                    continue
                message = event.get("message")
                if not isinstance(message, dict) or message.get("role") != "assistant":
                    continue
                key = _selector(message.get("provider"), message.get("model")) or "unknown"
                out.setdefault(key, _Usage()).add(message.get("usage"))
        return out

    def _sum_session_assistant(self, path: Path, acc: "_Usage") -> None:
        if not path.exists():
            return
        with path.open(errors="replace") as fh:
            for line in fh:
                entry = _loads(line)
                if not entry or entry.get("type") != "message":
                    continue
                message = entry.get("message")
                if isinstance(message, dict) and message.get("role") == "assistant":
                    acc.add(message.get("usage"))

    def _final_assistant_text(self, path: Path) -> str:
        latest = ""
        if not path.exists():
            return latest
        with path.open(errors="replace") as fh:
            for line in fh:
                event = _loads(line)
                if not event or event.get("type") != "message_end":
                    continue
                message = event.get("message")
                if not isinstance(message, dict) or message.get("role") != "assistant":
                    continue
                content = message.get("content")
                if not isinstance(content, list):
                    continue
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                        parts.append(block["text"])
                if parts:
                    latest = "\n".join(parts)
        return latest
