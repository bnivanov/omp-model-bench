import { appendFileSync } from "node:fs";
import type { HookAPI } from "@oh-my-pi/pi-coding-agent/extensibility/hooks";

let spawnCount = 0;

export default function benchmarkSpawnCap(pi: HookAPI): void {
  pi.on("tool_call", async (event) => {
    if (event.toolName !== "task") return;

    const maxSpawns = Number.parseInt(
      process.env.OMP_BENCH_MAX_SPAWNS ?? "0",
      10
    );

    if (!Number.isFinite(maxSpawns) || maxSpawns <= 0) {
      return {
        block: true,
        reason: "This benchmark architecture does not allow subagents."
      };
    }

    const allowedAgent =
      process.env.OMP_BENCH_ALLOWED_AGENT?.trim() ?? "";

    if (!allowedAgent) {
      return {
        block: true,
        reason: "Benchmark worker allowlist is not configured."
      };
    }

    const requestedAgent =
      typeof event.input.agent === "string"
        ? event.input.agent.trim()
        : "";

    if (requestedAgent !== allowedAgent) {
      return {
        block: true,
        reason:
          `This benchmark architecture only allows agent "${allowedAgent}".`
      };
    }

    if (spawnCount >= maxSpawns) {
      return {
        block: true,
        reason:
          `Benchmark worker limit reached: maximum ${maxSpawns} subagents.`
      };
    }

    spawnCount += 1;

    appendFileSync(
      "/logs/agent/benchmark-spawns.jsonl",
      JSON.stringify({
        spawn_index: spawnCount,
        agent: requestedAgent
      }) + "\n"
    );
  });
}
