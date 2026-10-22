from __future__ import annotations

import json
import io
import os
import subprocess
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from ai_bridge_kit import paid_review, text_transform as transform
from tests import test_text_transform


class TextTransformBudgetTests(unittest.TestCase):
    def project(self):
        values = test_text_transform.TextTransformTests().make_project()
        self.addCleanup(values[0].cleanup)
        return values

    def run_transform(self, values, opener):
        _, target, source, _, output, result = values
        return transform.run_text_transform(target, target / "results/048_text/text_transform/text_transform_inputs.json",
                                            source, output, result, api_key="fixture-only", opener=opener)

    def test_real_git_reservation_precedes_response_and_final_writeback_has_actual_ledger(self):
        values = self.project()
        tmp, target, *_ = values
        remote = Path(tmp.name) / "remote.git"
        for command in [["git", "init", "--bare", str(remote)], ["git", "config", "user.name", "fixture"],
                        ["git", "config", "user.email", "fixture@example.invalid"], ["git", "add", "."],
                        ["git", "commit", "-m", "fixture"], ["git", "remote", "add", "origin", str(remote)],
                        ["git", "push", "origin", "HEAD:refs/heads/fixture"]]:
            subprocess.run(command, cwd=target, check=True, capture_output=True)
        calls = []

        def opener(request, timeout):
            payload = json.loads(request.data)
            calls.append(request.full_url)
            if request.full_url.endswith("input_tokens"):
                return test_text_transform.FakeResponse({"input_tokens": 100})
            raw = subprocess.check_output(["git", "--git-dir", str(remote), "show",
                         "refs/heads/fixture:results/048_text/paid_review_budget.json"])
            saved = json.loads(raw)
            self.assertEqual(len(saved["reservations"]), 1)
            self.assertEqual(saved["contract"]["max_paid_calls"], 1)
            self.assertEqual(saved["contract"]["campaign_reserved_cost_hard_ceiling_usd"], "0.250000")
            self.assertEqual(payload["max_output_tokens"], 4096)
            self.assertEqual(payload["reasoning"], {"effort": "low"})
            self.assertEqual(payload["service_tier"], "default")
            self.assertFalse(payload["store"])
            self.assertEqual(payload["tools"], [])
            return test_text_transform.FakeResponse({"status": "completed", "output_text": "safe transformed output"})

        with mock.patch.dict(os.environ, {"AI_BRIDGE_PAID_REVIEW_GIT_RESERVE": "1", "GITHUB_REF_TYPE": "branch",
                                           "GITHUB_REF_NAME": "fixture"}):
            result = self.run_transform(values, opener)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["paid_review_receipt"]["accounting_status"], "ACCOUNTING_VERIFIED")
        _, _, _, _, output_path, result_path = values
        self.assertTrue(transform.text_transform_writeback_needed(target, output_path, result_path))
        paths = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=target, text=True).splitlines()
        self.assertEqual(paths, ["results/048_text/paid_review_budget.json",
                               "results/048_text/text_transform/TEXT_TRANSFORM.json",
                               "results/048_text/text_transform/output.age"])
        with self.assertRaisesRegex(transform.TextTransformError, "already exists"):
            self.run_transform(values, lambda *_a, **_k: self.fail("no rerun"))

    def test_failed_push_prevents_response_and_reservation_stays_spent(self):
        values = self.project()
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            self.assertTrue(request.full_url.endswith("input_tokens"))
            return test_text_transform.FakeResponse({"input_tokens": 100})

        with mock.patch.dict(os.environ, {"AI_BRIDGE_PAID_REVIEW_GIT_RESERVE": "1", "GITHUB_REF_TYPE": "branch",
                                           "GITHUB_REF_NAME": "fixture"}):
            with self.assertRaisesRegex(transform.TextTransformError, "writeback failed closed"):
                self.run_transform(values, opener)
        with self.assertRaisesRegex(transform.TextTransformError, "reservation consumed"):
            self.run_transform(values, opener)
        self.assertEqual(len(calls), 1)

    def test_errors_unknown_and_zero_billing_do_not_allow_second_count_or_paid_call(self):
        for failure in ["timeout", "credit_balance_exhausted", "empty"]:
            with self.subTest(failure=failure):
                values = self.project()
                calls = []

                def opener(request, timeout):
                    calls.append(request.full_url)
                    if request.full_url.endswith("input_tokens"):
                        return test_text_transform.FakeResponse({"input_tokens": 100})
                    if failure == "empty":
                        return test_text_transform.FakeResponse({"status": "completed", "output_text": " "})
                    if failure == "credit_balance_exhausted":
                        raise urllib.error.HTTPError(request.full_url, 429, failure, {},
                              io.BytesIO(b'{"error":{"code":"credit_balance_exhausted"}}'))
                    raise TimeoutError(failure)

                with self.assertRaises(transform.TextTransformError):
                    self.run_transform(values, opener)
                with self.assertRaisesRegex(transform.TextTransformError, "reservation consumed"):
                    self.run_transform(values, opener)
                self.assertEqual(len(calls), 2)

    def test_concurrent_invocations_cannot_repeat_token_count_or_paid_call(self):
        values = self.project()
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            return test_text_transform.FakeResponse({"status": "completed", "output_text": "safe output"})

        def invoke(_):
            try:
                return self.run_transform(values, opener)["schema"]
            except transform.TextTransformError:
                return "REFUSED"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(invoke, range(2)))
        self.assertEqual(sorted(results), sorted([transform.TEXT_TRANSFORM_RESULT_SCHEMA, "REFUSED"]))
        self.assertEqual(len(calls), 2)  # One token count + one Responses, not two of either.

    def test_template_serializes_branch_and_checks_out_current_spent_ledger(self):
        template = Path(transform.__file__).resolve().parents[1] / "templates/text_transform/github-actions/text-transform.yml"
        text = template.read_text()
        self.assertIn("ref: ${{ github.ref }}", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("AI_BRIDGE_PAID_REVIEW_GIT_RESERVE: '1'", text)
        self.assertIn("      - main\n      - 'reviewed/**'", text)
        self.assertNotIn("work/bridge-core--normal-entry-acceptance-text-transform", text)

    def test_overbudget_and_wrong_model_fail_before_paid_call(self):
        values = self.project()
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            return test_text_transform.FakeResponse({"input_tokens": 200000})

        with self.assertRaisesRegex(transform.TextTransformError, "ceiling"):
            self.run_transform(values, opener)
        self.assertEqual(len(calls), 1)
        _, target, source, _, output, result = values
        with self.assertRaisesRegex(transform.TextTransformError, "model"):
            transform.run_text_transform(target, target / "results/048_text/text_transform/text_transform_inputs.json",
                source, output, result, model="other", api_key="fixture", opener=lambda *_a, **_k: self.fail("no request"))


if __name__ == "__main__":
    unittest.main()
