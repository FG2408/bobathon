import json
from pathlib import Path

import pytest

from triage.engine import triage

DATA = Path(__file__).resolve().parent.parent / "data" / "mock_claims.json"
CLAIMS = json.loads(DATA.read_text(encoding="utf-8"))


def run(claim):
    return triage(claim["summary"], amount=claim["amount_sgd"], claim_type=claim["claim_type"])


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: c["id"])
def test_mock_claim_matches_expected(claim):
    result, expected = run(claim), claim["expected"]
    assert result["priority"] == expected["priority"]
    assert result["escalate"] == expected["escalate"]
    assert {f["flag"] for f in result["fraud_indicators"]} == set(expected["fraud_flags"])
    assert result["recommended_actions"]


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: c["id"])
def test_evidence_comes_from_the_claim_text(claim):
    text = " ".join(claim["summary"].split())
    result = run(claim)
    for item in result["fraud_indicators"] + result["risk_factors"]:
        if item["flag"] != "claim_amount":
            assert item["evidence"] in text


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: c["id"])
def test_deterministic(claim):
    assert run(claim) == run(claim)


def test_negated_injury_is_not_flagged():
    summary = ("Minor bump in a car park this morning. No injuries to anyone involved and the vehicle "
               "remains drivable. Photos of the damage and the other party's details are attached to "
               "this claim for review by the team.")
    result = triage(summary, amount=600)
    assert all(r["flag"] != "minor_injury" for r in result["risk_factors"])
    assert result["priority"] == "Low"
