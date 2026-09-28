"""Flask Blueprint — all routes for the triage app."""
import json
import sys
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, url_for

# The triage package lives one level above the app package (../triage)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from triage.engine import triage  # noqa: E402

from .db import get_all_claims, get_claim, save_claim

main = Blueprint("main", __name__)

CLAIM_TYPES = [
    "Motor",
    "Motor - Third Party Bodily Injury",
    "Home",
    "Commercial Property",
    "Travel Medical",
    "Health",
    "Liability",
    "Other / Unspecified",
]

AMOUNT_BANDS = [
    ("Under SGD 10,000",      9_000),
    ("SGD 10,000 – 50,000",  30_000),
    ("SGD 50,000 – 100,000", 75_000),
    ("SGD 100,000 – 250,000", 175_000),
    ("Over SGD 250,000",      300_000),
]


@main.route("/", methods=["GET"])
def index():
    return render_template("index.html", claim_types=CLAIM_TYPES, amount_bands=AMOUNT_BANDS)


@main.route("/score", methods=["POST"])
def score():
    claim_text = request.form.get("claim_text", "").strip()
    claim_type = request.form.get("claim_type") or None
    amount_band = request.form.get("amount_band") or None

    if not claim_text:
        flash("Please enter a claim summary.", "warning")
        return redirect(url_for("main.index"))

    # Resolve numeric amount from the chosen band label
    amount_sgd = None
    if amount_band:
        for label, value in AMOUNT_BANDS:
            if label == amount_band:
                amount_sgd = float(value)
                break

    result = triage(claim_text, amount=amount_sgd, claim_type=claim_type)
    row_id = save_claim(claim_text, claim_type, amount_band, amount_sgd, result)
    return redirect(url_for("main.result", claim_id=row_id))


@main.route("/result/<int:claim_id>")
def result(claim_id):
    row = get_claim(claim_id)
    if row is None:
        flash("Claim not found.", "danger")
        return redirect(url_for("main.index"))

    result = json.loads(row["result_json"])
    return render_template("result.html", row=row, result=result)


@main.route("/history")
def history():
    rows = get_all_claims()
    claims = []
    for row in rows:
        r = json.loads(row["result_json"])
        claims.append({
            "id": row["id"],
            "submitted_at": row["submitted_at"],
            "claim_type": row["claim_type"] or "—",
            "amount_band": row["amount_band"] or "—",
            "score": r["score"],
            "fraud_score": r["fraud_score"],
            "priority": r["priority"],
            "escalate": r["escalate"],
        })
    return render_template("history.html", claims=claims)
