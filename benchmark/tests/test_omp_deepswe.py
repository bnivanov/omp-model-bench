import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from benchmark.agents.omp_deepswe import OmpDeepSWE


class PrewalkReviewTreatmentTest(unittest.IsolatedAsyncioTestCase):
    async def test_prewalk_handoff_precedes_review_and_single_repair(self):
        agent = object.__new__(OmpDeepSWE)
        agent.treatment = "prewalk_review"
        agent.worker_model = "deepseek/deepseek-v4-flash"
        agent.prewalker_model = "kimi-code/k3"
        agent.benchmark_thinking = "max"
        agent.exec_as_agent = AsyncMock(
            return_value=SimpleNamespace(return_code=0, stdout=f"{'a' * 40}\n")
        )
        agent._entry_instruction = lambda _instruction: "entry"
        agent._run_stage = AsyncMock()
        agent._run_review_and_repair = AsyncMock()
        agent._capture_final_solution = AsyncMock()

        await agent._run_treatment("task", object())

        agent._run_stage.assert_awaited_once()
        stage = agent._run_stage.await_args.kwargs
        self.assertEqual(stage["role"], "prewalk_worker")
        self.assertEqual(stage["model"], "kimi-code/k3")
        self.assertEqual(
            stage["extra_args"],
            [
                "--prewalk",
                "--prewalk-into",
                "deepseek/deepseek-v4-flash:max",
            ],
        )
        agent._run_review_and_repair.assert_awaited_once()
        agent._capture_final_solution.assert_awaited_once()


class TimeoutFinalizationTest(unittest.IsolatedAsyncioTestCase):
    async def test_cancellation_attempts_final_capture_and_propagates(self):
        agent = object.__new__(OmpDeepSWE)
        agent._base_commit = "base"
        agent._run_treatment = AsyncMock(side_effect=asyncio.CancelledError)
        agent._capture_final_solution = AsyncMock()

        with self.assertRaises(asyncio.CancelledError):
            await OmpDeepSWE.run.__wrapped__(agent, "task", object(), object())

        agent._capture_final_solution.assert_awaited_once()

    async def test_wait_for_timeout_waits_for_final_capture(self):
        agent = object.__new__(OmpDeepSWE)
        agent._base_commit = "base"

        async def run_until_cancelled(*_args):
            await asyncio.sleep(60)

        agent._run_treatment = AsyncMock(side_effect=run_until_cancelled)
        agent._capture_final_solution = AsyncMock()

        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(
                OmpDeepSWE.run.__wrapped__(agent, "task", object(), object()),
                timeout=0.01,
            )

        agent._capture_final_solution.assert_awaited_once()

    async def test_capture_failure_does_not_replace_cancellation(self):
        agent = object.__new__(OmpDeepSWE)
        agent._base_commit = "base"
        agent._run_treatment = AsyncMock(side_effect=asyncio.CancelledError)
        agent._capture_final_solution = AsyncMock(
            side_effect=RuntimeError("capture failed")
        )

        with self.assertRaises(asyncio.CancelledError):
            await OmpDeepSWE.run.__wrapped__(agent, "task", object(), object())

        agent._capture_final_solution.assert_awaited_once()

    async def test_cancelled_stage_remains_registered_for_accounting(self):
        agent = object.__new__(OmpDeepSWE)
        agent.treatment = "advisor"
        agent.worker_model = "deepseek/deepseek-v4-flash"
        agent.planner_model = None
        agent.prewalker_model = None
        agent.advisor_model = "kimi-code/k3"
        agent._stage_records = []
        agent._execute_omp = AsyncMock(side_effect=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            await agent._run_stage(
                object(),
                role="worker",
                label="worker",
                instruction="task",
                model=agent.worker_model,
                tools=["read"],
            )

        self.assertEqual(len(agent._stage_records), 1)
        self.assertIsNone(agent._stage_records[0]["return_code"])

    def test_partial_advisor_transcript_reconciles_after_timeout(self):
        root = Path(tempfile.mkdtemp(prefix="advisor-accounting-"))
        advisor_dir = root / "sessions" / "worker" / "session"
        advisor_dir.mkdir(parents=True)
        worker_message = {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "usage": {
                    "input": 1,
                    "cacheRead": 2,
                    "cacheWrite": 0,
                    "output": 3,
                    "cost": {"total": 0.4},
                },
            },
        }
        advisor_message = {
            "type": "message",
            "message": {
                "role": "assistant",
                "provider": "kimi-code",
                "model": "k3",
                "usage": {
                    "input": 4,
                    "cacheRead": 5,
                    "cacheWrite": 0,
                    "output": 6,
                    "cost": {"total": 0},
                },
            },
        }
        (root / "worker.jsonl").write_text(json.dumps(worker_message) + "\n")
        (advisor_dir / "__advisor.jsonl").write_text(json.dumps(advisor_message) + "\n")

        agent = object.__new__(OmpDeepSWE)
        agent.logs_dir = root
        agent.treatment = "advisor"
        agent.worker_model = "deepseek/deepseek-v4-flash"
        agent.planner_model = None
        agent.prewalker_model = None
        agent.advisor_model = "kimi-code/k3"
        agent.reviewer_model = None
        agent.prompt_scaffold = "none"
        agent.benchmark_thinking = "max"
        agent.advisor_sync_backlog = 1
        agent.advisor_immune_turns = 3
        agent.repair_passes = 1
        agent._stage_records = [
            {
                "role": "worker",
                "label": "worker",
                "kind": "normal",
                "output_filename": "worker.jsonl",
                "expected_models": [agent.worker_model, agent.advisor_model],
                "return_code": None,
            }
        ]
        context = SimpleNamespace(
            n_input_tokens=None,
            n_output_tokens=None,
            n_cache_tokens=None,
            cost_usd=None,
            metadata=None,
        )

        agent.populate_context_post_run(context)

        self.assertEqual(context.n_input_tokens, 12)
        self.assertEqual(context.n_cache_tokens, 7)
        self.assertEqual(context.n_output_tokens, 9)
        self.assertEqual(set(context.metadata["stages"]), {"worker", "advisor"})

    async def test_omp_cancellation_stops_process_group_before_capture(self):
        agent = object.__new__(OmpDeepSWE)
        agent._binary = True
        agent._cli = "/installed-agent/omp"
        agent._auto_approve = True
        agent._thinking = "max"
        agent._agent_args = []
        agent._gateway_on = True
        agent._forward_env = {}
        agent.exec_as_agent = AsyncMock(
            side_effect=[
                SimpleNamespace(return_code=0),
                asyncio.CancelledError(),
                SimpleNamespace(return_code=0),
            ]
        )

        with self.assertRaises(asyncio.CancelledError):
            await agent._execute_omp(
                "task",
                object(),
                model_name="deepseek/deepseek-v4-flash",
                output_filename="worker.jsonl",
                session_dir="/logs/agent/sessions/worker",
            )

        launch = agent.exec_as_agent.await_args_list[1].kwargs["command"]
        cleanup = agent.exec_as_agent.await_args_list[2].kwargs["command"]
        self.assertIn("setsid sh -c", launch)
        self.assertIn(".worker.jsonl.pid", launch)
        self.assertIn("kill -TERM", cleanup)
        self.assertIn("kill -KILL", cleanup)

    async def test_failed_process_cleanup_blocks_timeout_capture(self):
        agent = object.__new__(OmpDeepSWE)
        agent._binary = True
        agent._cli = "/installed-agent/omp"
        agent._auto_approve = True
        agent._thinking = "max"
        agent._agent_args = []
        agent._gateway_on = True
        agent._forward_env = {}
        agent.exec_as_agent = AsyncMock(
            side_effect=[
                SimpleNamespace(return_code=0),
                asyncio.CancelledError(),
                SimpleNamespace(return_code=1),
            ]
        )
        with self.assertRaises(asyncio.CancelledError):
            await agent._execute_omp(
                "task",
                object(),
                model_name="deepseek/deepseek-v4-flash",
                output_filename="worker.jsonl",
                session_dir="/logs/agent/sessions/worker",
            )

        self.assertFalse(agent._workspace_stable_on_failure)

    async def test_cancelled_clean_workspace_recovers_single_new_stash(self):
        old_stash = "a" * 40
        new_stash = "b" * 40
        agent = object.__new__(OmpDeepSWE)
        agent._base_stashes = {old_stash}
        agent.exec_as_agent = AsyncMock(
            side_effect=[
                SimpleNamespace(
                    return_code=0,
                    stdout=f"tracked_dirty=0\n{new_stash}\n{old_stash}\n",
                ),
                SimpleNamespace(return_code=0),
            ]
        )

        recovered = await agent._recover_cancelled_stash(object())

        self.assertEqual(recovered, new_stash)
        self.assertIn(
            new_stash, agent.exec_as_agent.await_args_list[1].kwargs["command"]
        )

    async def test_cancelled_dirty_workspace_rejects_ambiguous_stash(self):
        new_stash = "b" * 40
        agent = object.__new__(OmpDeepSWE)
        agent._base_stashes = set()
        agent.exec_as_agent = AsyncMock(
            return_value=SimpleNamespace(
                return_code=0,
                stdout=f"tracked_dirty=1\n{new_stash}\n",
            )
        )

        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            await agent._recover_cancelled_stash(object())

        agent.exec_as_agent.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
