from __future__ import annotations

import concurrent.futures
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ai_bridge_kit import paid_review


class PaidReviewBudgetTests(unittest.TestCase):
    def request_payload(self) -> dict:
        return {
            "model": paid_review.DEFAULT_MODEL,
            "store": False,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": "Review this."}]}],
            "max_output_tokens": paid_review.DEFAULT_MAX_OUTPUT_TOKENS,
        }

    def token_preflight(self, input_tokens: int = 1000) -> dict:
        return {
            "endpoint": "/responses/input_tokens",
            "input_tokens": input_tokens,
            "raw_response": {"input_tokens": input_tokens},
        }

    def reserve(self, target: Path, *, campaign: str = "001_paid", input_tokens: int = 1000) -> dict:
        return paid_review.reserve_paid_review_call(
            target=target,
            campaign_identity=campaign,
            review_type="text_review",
            model=paid_review.DEFAULT_MODEL,
            request_payload=self.request_payload(),
            input_token_preflight=self.token_preflight(input_tokens),
        )

    def test_default_contract_matches_frozen_paid_review_policy(self) -> None:
        contract = paid_review.default_contract()
        self.assertEqual(contract["model"], "gpt-5.6-terra")
        self.assertEqual(contract["max_paid_calls"], 2)
        self.assertEqual(contract["campaign_reserved_cost_hard_ceiling_usd"], "0.500000")
        self.assertEqual(contract["per_call_worst_case_ceiling_usd"], "0.250000")
        self.assertEqual(contract["automatic_paid_retries"], 0)
        self.assertEqual(contract["pricing"]["input_usd_per_1m_tokens"], "2.000000")
        self.assertEqual(contract["pricing"]["cached_input_usd_per_1m_tokens"], "0.200000")
        self.assertEqual(contract["pricing"]["output_usd_per_1m_tokens"], "12.000000")
        self.assertTrue(contract["pricing"]["runtime_uses_uncached_input_price"])

    def test_reservation_persists_across_restart_or_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            first = self.reserve(target)
            state_path = target / "results/001_paid/paid_review_budget.json"
            self.assertEqual(first["state_path"], state_path)
            reloaded = paid_review.load_budget_state(state_path, campaign_identity="001_paid")
            self.assertEqual(len(reloaded["reservations"]), 1)
            second = self.reserve(target)
            self.assertEqual(second["reservation"]["call_number"], 2)
            self.assertEqual(len(paid_review.load_budget_state(state_path, campaign_identity="001_paid")["reservations"]), 2)

    def test_max_call_count_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self.reserve(target)
            self.reserve(target)
            with self.assertRaisesRegex(paid_review.PaidReviewBudgetError, "call limit exhausted"):
                self.reserve(target)

    def test_per_call_ceiling_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            with self.assertRaisesRegex(paid_review.PaidReviewBudgetError, "per-call"):
                self.reserve(target, input_tokens=101_000)
            self.assertFalse((target / "results/001_paid/paid_review_budget.json").exists())

    def test_campaign_ceiling_fails_closed_from_persistent_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            state_path = target / "results/001_paid/paid_review_budget.json"
            state_path.parent.mkdir(parents=True)
            state = {
                "schema": paid_review.BUDGET_SCHEMA,
                "campaign_identity": "001_paid",
                "contract": paid_review.default_contract(),
                "reservations": [{"worst_case_reserved_cost_usd": "0.490000"}],
            }
            state_path.write_text(paid_review.canonical_json(state, pretty=True), encoding="utf-8")
            with self.assertRaisesRegex(paid_review.PaidReviewBudgetError, "campaign reserved-cost"):
                self.reserve(target)

    def test_model_pricing_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            with self.assertRaisesRegex(paid_review.PaidReviewBudgetError, "model/pricing mismatch"):
                paid_review.reserve_paid_review_call(
                    target=target,
                    campaign_identity="001_paid",
                    review_type="text_review",
                    model="gpt-5.6-luna",
                    request_payload={**self.request_payload(), "model": "gpt-5.6-luna"},
                    input_token_preflight=self.token_preflight(),
                )

    def test_same_campaign_concurrency_does_not_double_spend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)

            def attempt(index: int) -> str:
                try:
                    bundle = self.reserve(target, input_tokens=1000 + index)
                    return bundle["reservation"]["reservation_id"]
                except paid_review.PaidReviewBudgetError as exc:
                    return str(exc)

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                results = list(pool.map(attempt, range(3)))

            successful = [item for item in results if item.startswith("001_paid-")]
            failed = [item for item in results if "call limit exhausted" in item]
            state = json.loads((target / "results/001_paid/paid_review_budget.json").read_text(encoding="utf-8"))
            self.assertEqual(len(successful), 2, results)
            self.assertEqual(len(failed), 1, results)
            self.assertEqual(len(state["reservations"]), 2)
            self.assertEqual(
                state["reservations"][-1]["cumulative_reserved_cost_usd"],
                state["reservations"][1]["cumulative_reserved_cost_usd"],
            )

    def test_github_reservation_writeback_pushes_before_paid_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            state_path = target / "results/001_paid/paid_review_budget.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text("{}\n", encoding="utf-8")
            calls: list[list[str]] = []

            def fake_run(command, **_kwargs):
                calls.append(command)
                return subprocess_result(0)

            with mock.patch.dict(
                "os.environ",
                {
                    "AI_BRIDGE_PAID_REVIEW_GIT_RESERVE": "1",
                    "GITHUB_REF_TYPE": "branch",
                    "GITHUB_REF_NAME": "reviewed/task",
                },
            ), mock.patch("ai_bridge_kit.paid_review.subprocess.run", side_effect=fake_run):
                paid_review.persist_reservation_to_git_if_requested(target, state_path)

            self.assertEqual(calls[2], ["git", "add", "--", "results/001_paid/paid_review_budget.json"])
            self.assertEqual(calls[3], ["git", "commit", "-m", "Reserve AI Bridge paid review budget"])
            self.assertEqual(calls[4], ["git", "push", "origin", "HEAD:reviewed/task"])


def subprocess_result(returncode: int):
    completed = mock.Mock()
    completed.returncode = returncode
    completed.stdout = ""
    completed.stderr = ""
    return completed


if __name__ == "__main__":
    unittest.main()
