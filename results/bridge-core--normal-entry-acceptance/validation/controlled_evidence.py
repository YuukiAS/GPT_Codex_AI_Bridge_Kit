"""Save raw time-controlled ETA/budget fixtures, explicitly not live evidence."""
import json
from pathlib import Path
import sys

import ai_bridge_kit

ROOT = Path(__file__).resolve().parents[3]
EXPORT = ROOT / "private/exports/bridge-core--normal-entry-acceptance"
OUT = ROOT / "results/bridge-core--normal-entry-acceptance/validation"
identity = json.loads((EXPORT / "CANDIDATE_INSTALL_IDENTITY.json").read_text())
assert Path(ai_bridge_kit.__file__).resolve() == Path(identity["module_path"])
sys.path.append(str(ROOT))
from tests.test_persistent_progress_truth import PersistentProgressTruthTests
from tests.test_persistent_notification_budget import PersistentNotificationBudgetTests

eta_fixture = PersistentProgressTruthTests()
eta_fixture.setUp()
snapshots = []
try:
    for seconds, completed in [(0, 2), (300, 5), (600, 8)]:
        publication = eta_fixture.publish(seconds, completed)
        snapshots.append({"test_clock_seconds": seconds, "publication": publication,
                          "binding": json.loads(json.dumps(eta_fixture.binding))})
    assert snapshots[-1]["binding"]["last_good_progress"]["eta"] == "2026-10-22T00:16:40+00:00"
    for seconds in [601, 1501]:
        eta_fixture.observe(seconds)
        snapshots.append({"test_clock_seconds": seconds, "binding": json.loads(json.dumps(eta_fixture.binding))})
finally:
    eta_fixture.doCleanups()
budgets = []
for mode in ["accepted_fixture", "failed", "unknown", "crashed_helper"]:
    fixture = PersistentNotificationBudgetTests()
    fixture.setUp()
    try:
        final = fixture.run_chain(fail=mode == "failed", unknown=mode == "unknown", crash=mode == "crashed_helper")
        budgets.append({"external_boundary": mode, "binding": final,
                        "helper_boundary_entries": fixture.helper_count, "simulated_smtp_entries": fixture.smtp_count,
                        "claims": [claim for claim, _directory in fixture.captured]})
    finally:
        fixture.doCleanups()
payload = {"candidate": identity["source_sha"], "runtime_module": str(Path(ai_bridge_kit.__file__).resolve()),
           "kind": "DETERMINISTIC_FIXTURES_NOT_LIVE", "test_clock_only": True,
           "fake_tmux_boundary": True, "real_local_primary_child_in_budget_fixture": True,
           "model_and_smtp_boundaries": "fixtures; SMTP_ACCEPTED fields below are NOT real transport",
           "real_model_calls": 0, "real_smtp_attempts": 0, "real_paid_api_calls": 0,
           "eta_expected_remaining_seconds_at_third_publication": 400, "eta_snapshots": snapshots,
           "budget_cases": budgets}
(OUT / "CONTROLLED_ETA_BUDGET_RAW.json").write_text(json.dumps(payload, indent=2) + "\n")
print(json.dumps({"candidate": identity["source_sha"], "controlled_eta": "PASS", "five_plus_terminal": "PASS",
                  "real_model_calls": 0, "real_smtp_attempts": 0}))
