import json
import tempfile
import unittest
from pathlib import Path

from benchmark.scripts.validate_run import (
    expected_stages,
    validate_finalization,
    validate_result,
)


class TreatmentStageValidationTest(unittest.TestCase):
    def test_prewalk_review_requires_handoff_review_and_repair_stages(self):
        condition = {
            "treatment": "prewalk_review",
            "worker_model": "deepseek/deepseek-v4-flash",
            "prewalker_model": "kimi-code/k3",
            "reviewer_model": "kimi-code/k3",
        }

        self.assertEqual(
            expected_stages(condition),
            {
                "prewalk_worker.jsonl": {
                    "deepseek/deepseek-v4-flash",
                    "kimi-code/k3",
                },
                "reviewer.jsonl": {"kimi-code/k3"},
                "repair.jsonl": {"deepseek/deepseek-v4-flash"},
            },
        )


class TimeoutResultValidationTest(unittest.TestCase):
    def fixture(self, exception_type="AgentTimeoutError"):
        root = Path(tempfile.mkdtemp(prefix="timeout-result-"))
        trial_dir = root / "trial"
        trial_dir.mkdir()
        timed_out = exception_type == "AgentTimeoutError"
        (root / "result.json").write_text(
            json.dumps(
                {
                    "n_total_trials": 1,
                    "stats": {
                        "n_completed_trials": 1,
                        "n_errored_trials": 1 if exception_type else 0,
                        "n_running_trials": 0,
                        "n_pending_trials": 0,
                        "n_cancelled_trials": 0,
                        "n_retries": 0,
                    },
                }
            )
        )
        exception_info = None
        if exception_type:
            exception_info = {
                "exception_type": exception_type,
                "exception_message": (
                    "Agent execution timed out after 5400.0 seconds"
                    if timed_out
                    else "provider failed"
                ),
            }
        stages = {
            "worker": {
                "input_tokens": 1,
                "cache_read_tokens": 2,
                "cache_write_tokens": 0,
                "output_tokens": 3,
                "cost_usd": 0.4,
            },
            "advisor": {
                "input_tokens": 4,
                "cache_read_tokens": 5,
                "cache_write_tokens": 0,
                "output_tokens": 6,
                "cost_usd": 0.0,
            },
        }
        (trial_dir / "result.json").write_text(
            json.dumps(
                {
                    "exception_info": exception_info,
                    "agent_execution": {
                        "started_at": "2026-08-13T08:00:00Z",
                        "finished_at": "2026-08-13T09:30:00Z",
                    },
                    "agent_result": {
                        "n_input_tokens": 12,
                        "n_cache_tokens": 7,
                        "n_output_tokens": 9,
                        "cost_usd": 0.4,
                        "metadata": {"stages": stages},
                    },
                }
            )
        )
        return root

    def test_clean_timeout_is_a_model_outcome(self):
        violations = []
        evidence = {}

        model_timeout = validate_result(
            self.fixture(), {"treatment": "advisor"}, violations, evidence
        )

        self.assertTrue(model_timeout)
        self.assertEqual(violations, [])
        self.assertIn("model_timeout", evidence)
        self.assertEqual(evidence["stage_accounting"]["reported"]["input_tokens"], 12)

    def test_clean_completion_reconciles(self):
        violations = []

        model_timeout = validate_result(
            self.fixture(None), {"treatment": "advisor"}, violations, {}
        )

        self.assertFalse(model_timeout)
        self.assertEqual(violations, [])

    def test_non_timeout_exception_is_harness_invalid(self):
        violations = []

        model_timeout = validate_result(
            self.fixture("RuntimeError"), {"treatment": "advisor"}, violations, {}
        )

        self.assertFalse(model_timeout)
        self.assertTrue(any("RuntimeError" in violation for violation in violations))

    def test_timeout_finalization_accepts_recovered_stash(self):
        root = Path(tempfile.mkdtemp(prefix="timeout-finalization-"))
        agent_dir = root / "trial" / "agent"
        agent_dir.mkdir(parents=True)
        record = {
            "base_commit": "a" * 40,
            "final_commit": "b" * 40,
            "recovered_cancelled_stash": "c" * 40,
        }
        (agent_dir / "finalization.json").write_text(json.dumps(record))
        violations = []
        evidence = {}

        validate_finalization(root, True, violations, evidence)

        self.assertEqual(violations, [])
        self.assertEqual(evidence["finalization"], record)

    def test_normal_completion_rejects_cancelled_stash_recovery(self):
        root = Path(tempfile.mkdtemp(prefix="normal-finalization-"))
        agent_dir = root / "trial" / "agent"
        agent_dir.mkdir(parents=True)
        record = {
            "base_commit": "a" * 40,
            "final_commit": "b" * 40,
            "recovered_cancelled_stash": "c" * 40,
        }
        (agent_dir / "finalization.json").write_text(json.dumps(record))
        violations = []

        validate_finalization(root, False, violations, {})

        self.assertIn(
            "cancelled stash recovery occurred without a model timeout", violations
        )


if __name__ == "__main__":
    unittest.main()
