from __future__ import annotations

import concurrent.futures
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import io
import urllib.error

from ai_bridge_kit import paid_review


class PaidReviewBudgetTests(unittest.TestCase):
    def request_payload(self) -> dict:
        return {
            "model": paid_review.DEFAULT_MODEL,
            "store": False,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": "Review this."}]}],
            **paid_review.request_safety_fields(),
        }

    def token_preflight(self, input_tokens: int = 1000) -> dict:
        return {
            "endpoint": "/v1/responses/input_tokens",
            "input_tokens": input_tokens,
            "raw_response": {"input_tokens": input_tokens},
        }

    def response_payload(
        self,
        *,
        input_tokens: int = 100,
        cached_tokens: int = 0,
        cache_write_tokens: int = 0,
        output_tokens: int = 20,
        reasoning_tokens: int = 0,
        model: str = paid_review.DEFAULT_MODEL,
        service_tier: str = paid_review.DEFAULT_SERVICE_TIER,
    ) -> dict:
        return {
            "id": "resp_paid_review_test",
            "model": model,
            "service_tier": service_tier,
            "usage": {
                "input_tokens": input_tokens,
                "input_tokens_details": {
                    "cached_tokens": cached_tokens,
                    "cache_write_tokens": cache_write_tokens,
                },
                "output_tokens": output_tokens,
                "output_tokens_details": {"reasoning_tokens": reasoning_tokens},
            },
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
        self.assertEqual(contract["pricing"]["cache_write_input_usd_per_1m_tokens"], "2.500000")
        self.assertEqual(contract["pricing"]["worst_case_input_usd_per_1m_tokens"], "2.500000")
        self.assertEqual(contract["pricing"]["output_usd_per_1m_tokens"], "12.000000")
        self.assertEqual(contract["pricing"]["long_context_threshold"], 272_000)
        self.assertTrue(contract["pricing"]["runtime_uses_worst_case_input_price"])

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

    def test_long_context_input_fails_closed_before_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            with self.assertRaisesRegex(paid_review.PaidReviewBudgetError, "long-context pricing boundary"):
                self.reserve(target, input_tokens=272_001)
            self.assertFalse((target / "results/001_paid/paid_review_budget.json").exists())

    def test_worst_case_input_uses_cache_write_price(self) -> None:
        cost = paid_review.calculate_worst_case_cost(1000, 1000)
        self.assertEqual(paid_review._money(cost), "0.014500")

    def test_count_input_tokens_uses_provider_compatible_projection(self) -> None:
        captured: dict = {}

        def opener(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return fake_response({"input_tokens": 10})

        image_content = {"type": "input_image", "image_url": "data:image/png;base64,abc123"}
        text_schema = {"format": {"type": "json_schema", "name": "review", "schema": {"type": "object"}}}
        payload = {
            **self.request_payload(),
            "conversation": "conv_123",
            "input": [{"role": "user", "content": [{"type": "input_text", "text": "Review this."}, image_content]}],
            "instructions": "Count this request.",
            "parallel_tool_calls": False,
            "personality": "concise",
            "previous_response_id": "resp_previous",
            "text": text_schema,
            "tool_choice": "none",
            "truncation": "disabled",
        }
        result = paid_review.count_input_tokens(payload, api_key="sk-test", opener=opener)
        self.assertEqual(result["input_tokens"], 10)
        expected = {
            "conversation": payload["conversation"],
            "input": payload["input"],
            "instructions": payload["instructions"],
            "model": payload["model"],
            "parallel_tool_calls": payload["parallel_tool_calls"],
            "personality": payload["personality"],
            "previous_response_id": payload["previous_response_id"],
            "reasoning": payload["reasoning"],
            "text": payload["text"],
            "tool_choice": payload["tool_choice"],
            "tools": payload["tools"],
            "truncation": payload["truncation"],
        }
        self.assertEqual(captured["body"], expected)
        self.assertEqual(captured["body"]["input"][0]["content"][1], image_content)
        self.assertEqual(captured["body"]["text"], text_schema)
        self.assertEqual(captured["body"]["reasoning"], {"effort": paid_review.DEFAULT_REASONING_EFFORT})
        self.assertEqual(captured["body"]["tools"], [])
        for omitted in ("max_output_tokens", "service_tier", "store", "prompt_cache_options"):
            self.assertNotIn(omitted, captured["body"])

        canonical_request = json.loads(paid_review.canonical_json(payload))
        self.assertEqual(canonical_request["max_output_tokens"], paid_review.DEFAULT_MAX_OUTPUT_TOKENS)
        self.assertEqual(canonical_request["service_tier"], paid_review.DEFAULT_SERVICE_TIER)
        self.assertFalse(canonical_request["store"])
        self.assertEqual(canonical_request["prompt_cache_options"], {"mode": "explicit"})

    def test_input_token_http_error_reports_openai_code(self) -> None:
        def opener(request, timeout):
            body = json.dumps({"error": {"code": "missing_scope"}}).encode("utf-8")
            raise urllib.error.HTTPError(request.full_url, 403, "forbidden", {}, io.BytesIO(body))

        with self.assertRaisesRegex(paid_review.PaidReviewBudgetError, "HTTP 403 \\(missing_scope\\)"):
            paid_review.count_input_tokens(self.request_payload(), api_key="sk-test", opener=opener)

    def test_actual_usage_cost_is_persisted_and_cache_write_is_verified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            first = self.reserve(target)
            paid_review.record_actual_usage(
                target=target,
                campaign_identity="001_paid",
                reservation_id=first["reservation"]["reservation_id"],
                response_payload=self.response_payload(input_tokens=100, cached_tokens=10, cache_write_tokens=5, output_tokens=20),
            )
            state = json.loads((target / "results/001_paid/paid_review_budget.json").read_text(encoding="utf-8"))
            reservation = state["reservations"][0]
            self.assertEqual(reservation["accounting_status"], "ACCOUNTING_VERIFIED")
            self.assertEqual(reservation["actual_model_cost_usd"], "0.000425")

    def test_accounting_unverified_blocks_next_paid_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            first = self.reserve(target)
            paid_review.record_actual_usage(
                target=target,
                campaign_identity="001_paid",
                reservation_id=first["reservation"]["reservation_id"],
                response_payload=self.response_payload(model="gpt-5.6-sol"),
            )
            state = json.loads((target / "results/001_paid/paid_review_budget.json").read_text(encoding="utf-8"))
            self.assertEqual(state["reservations"][0]["accounting_status"], "ACCOUNTING_UNVERIFIED")
            with self.assertRaisesRegex(paid_review.PaidReviewBudgetError, "accounting is unverified"):
                self.reserve(target)

    def test_actual_cost_never_refunds_reserved_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            first = self.reserve(target, input_tokens=1000)
            paid_review.record_actual_usage(
                target=target,
                campaign_identity="001_paid",
                reservation_id=first["reservation"]["reservation_id"],
                response_payload=self.response_payload(input_tokens=1, output_tokens=1),
            )
            state = json.loads((target / "results/001_paid/paid_review_budget.json").read_text(encoding="utf-8"))
            self.assertEqual(state["cumulative_reserved_worst_case_cost_usd"], "0.051652")
            self.assertEqual(state["cumulative_actual_model_cost_usd"], "0.000014")
            self.reserve(target, input_tokens=1000)
            with self.assertRaisesRegex(paid_review.PaidReviewBudgetError, "call limit exhausted"):
                self.reserve(target, input_tokens=1000)

    def test_actual_cost_formula_normal_cached_cache_write_and_mixed_tokens(self) -> None:
        cases = [
            (self.response_payload(input_tokens=100, output_tokens=20), "0.000440"),
            (self.response_payload(input_tokens=100, cached_tokens=40, output_tokens=20), "0.000368"),
            (self.response_payload(input_tokens=100, cached_tokens=10, cache_write_tokens=5, output_tokens=20), "0.000425"),
            (self.response_payload(input_tokens=1000, cached_tokens=200, cache_write_tokens=100, output_tokens=50), "0.002290"),
        ]
        for payload, expected in cases:
            with self.subTest(expected=expected):
                accounting = paid_review.verified_actual_accounting(
                    payload,
                    expected_model=paid_review.DEFAULT_MODEL,
                    expected_service_tier=paid_review.DEFAULT_SERVICE_TIER,
                )
                self.assertEqual(accounting["actual_model_cost_usd"], expected)

    def test_reasoning_tokens_are_not_double_counted(self) -> None:
        no_reasoning = paid_review.verified_actual_accounting(
            self.response_payload(input_tokens=100, output_tokens=20, reasoning_tokens=0),
            expected_model=paid_review.DEFAULT_MODEL,
            expected_service_tier=paid_review.DEFAULT_SERVICE_TIER,
        )
        with_reasoning = paid_review.verified_actual_accounting(
            self.response_payload(input_tokens=100, output_tokens=20, reasoning_tokens=20),
            expected_model=paid_review.DEFAULT_MODEL,
            expected_service_tier=paid_review.DEFAULT_SERVICE_TIER,
        )
        self.assertEqual(with_reasoning["actual_model_cost_usd"], no_reasoning["actual_model_cost_usd"])

    def test_malformed_required_usage_fails_closed(self) -> None:
        payload = self.response_payload()
        payload["usage"]["input_tokens"] = "100"
        with self.assertRaisesRegex(paid_review.PaidReviewBudgetError, "malformed required usage field"):
            paid_review.verified_actual_accounting(
                payload,
                expected_model=paid_review.DEFAULT_MODEL,
                expected_service_tier=paid_review.DEFAULT_SERVICE_TIER,
            )

    def test_negative_token_decomposition_fails_closed(self) -> None:
        with self.assertRaisesRegex(paid_review.PaidReviewBudgetError, "negative token decomposition"):
            paid_review.verified_actual_accounting(
                self.response_payload(input_tokens=10, cached_tokens=8, cache_write_tokens=5),
                expected_model=paid_review.DEFAULT_MODEL,
                expected_service_tier=paid_review.DEFAULT_SERVICE_TIER,
            )

    def test_wrong_model_and_unexpected_service_tier_fail_closed(self) -> None:
        with self.assertRaisesRegex(paid_review.PaidReviewBudgetError, "wrong response model"):
            paid_review.verified_actual_accounting(
                self.response_payload(model="gpt-5.6-sol"),
                expected_model=paid_review.DEFAULT_MODEL,
                expected_service_tier=paid_review.DEFAULT_SERVICE_TIER,
            )
        with self.assertRaisesRegex(paid_review.PaidReviewBudgetError, "unexpected service tier"):
            paid_review.verified_actual_accounting(
                self.response_payload(service_tier="flex"),
                expected_model=paid_review.DEFAULT_MODEL,
                expected_service_tier=paid_review.DEFAULT_SERVICE_TIER,
            )

    def test_unknown_positive_token_category_fails_closed(self) -> None:
        payload = self.response_payload()
        payload["usage"]["input_tokens_details"]["mystery_tokens"] = 1
        with self.assertRaisesRegex(paid_review.PaidReviewBudgetError, "unknown input token category"):
            paid_review.verified_actual_accounting(
                payload,
                expected_model=paid_review.DEFAULT_MODEL,
                expected_service_tier=paid_review.DEFAULT_SERVICE_TIER,
            )

    def test_zero_billing_failure_preserves_and_reuses_matching_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            first = self.reserve(target)
            paid_review.record_zero_billing_failure(
                target=target,
                campaign_identity="001_paid",
                reservation_id=first["reservation"]["reservation_id"],
                error_code="credit_balance_exhausted",
                http_status=429,
            )

            retry = self.reserve(target)
            state = json.loads((target / "results/001_paid/paid_review_budget.json").read_text(encoding="utf-8"))
            self.assertTrue(retry["reused_zero_billing_reservation"])
            self.assertEqual(retry["reservation"]["reservation_id"], first["reservation"]["reservation_id"])
            self.assertEqual(len(state["reservations"]), 1)
            self.assertEqual(state["reservations"][0]["actual_cost_status"], "ZERO_BILLING_FAILURE")
            self.assertEqual(state["reservations"][0]["actual_model_cost_usd"], "0.000000")
            self.assertFalse(state["reservations"][0]["failure"]["automatic_paid_retry"])

    def test_zero_billing_reuse_requires_same_request_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            first = self.reserve(target)
            paid_review.record_zero_billing_failure(
                target=target,
                campaign_identity="001_paid",
                reservation_id=first["reservation"]["reservation_id"],
                error_code="credit_balance_exhausted",
                http_status=429,
            )
            changed_payload = {**self.request_payload(), "input": [{"role": "user", "content": [{"type": "input_text", "text": "Different."}]}]}
            second = paid_review.reserve_paid_review_call(
                target=target,
                campaign_identity="001_paid",
                review_type="text_review",
                model=paid_review.DEFAULT_MODEL,
                request_payload=changed_payload,
                input_token_preflight=self.token_preflight(),
            )
            self.assertEqual(second["reservation"]["call_number"], 2)

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
                if command[:4] == ["git", "diff", "--cached", "--quiet"]:
                    return subprocess_result(1)
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
            self.assertEqual(calls[3], ["git", "diff", "--cached", "--quiet", "--", "results/001_paid/paid_review_budget.json"])
            self.assertEqual(calls[4], ["git", "commit", "-m", "Reserve AI Bridge paid review budget"])
            self.assertEqual(calls[5], ["git", "push", "origin", "HEAD:reviewed/task"])

    def test_github_reservation_writeback_noops_when_budget_is_unchanged(self) -> None:
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

            self.assertEqual(calls[-1], ["git", "diff", "--cached", "--quiet", "--", "results/001_paid/paid_review_budget.json"])


def subprocess_result(returncode: int):
    completed = mock.Mock()
    completed.returncode = returncode
    completed.stdout = ""
    completed.stderr = ""
    return completed


def fake_response(payload: dict):
    response = mock.Mock()
    response.__enter__ = mock.Mock(return_value=response)
    response.__exit__ = mock.Mock(return_value=False)
    response.read.return_value = json.dumps(payload).encode("utf-8")
    return response


if __name__ == "__main__":
    unittest.main()
