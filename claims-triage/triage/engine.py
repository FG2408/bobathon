"""Claims triage engine.

Deterministic and rule-based: the same claim always gets the same result, and every
flag is tied to the phrase in the claim that triggered it. All rules, weights and
thresholds live in config.json so they can be tuned without touching this code.

Usage:
    from triage.engine import triage
    result = triage("Fire in the storeroom ...", amount=400000)

    python -m triage.engine                 # run all mock claims
    python -m triage.engine "claim text"    # triage one claim, print JSON
"""
import json
import re
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("config.json")
PRIORITY_ORDER = ["Low", "Medium", "High", "Critical"]
NEGATORS = {"no", "not", "without", "zero", "nil", "none", "nobody", "neither", "never"}
BOUNDARIES = ".;!?\n"


def load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _sentence_start(text, pos):
    return max(text.rfind(c, 0, pos) for c in BOUNDARIES) + 1


def _sentence_end(text, pos):
    ends = [i for i in (text.find(c, pos) for c in BOUNDARIES) if i != -1]
    return min(ends) + 1 if ends else len(text)


def _is_negated(text, start):
    """True if one of the 3 words before `start` (same sentence) is a negator, e.g. 'No injuries'."""
    words = re.findall(r"[a-z']+", text[_sentence_start(text, start):start].lower())
    return any(w in NEGATORS for w in words[-3:])


def _detect(text, signals, negation_aware):
    hits = []
    for signal in signals:
        for pattern in signal["patterns"]:
            match = next(
                (m for m in re.finditer(pattern, text, re.IGNORECASE)
                 if not (negation_aware and _is_negated(text, m.start()))),
                None,
            )
            if match:
                evidence = text[_sentence_start(text, match.start()):_sentence_end(text, match.end())].strip()
                hits.append({**signal, "evidence": evidence})
                break
    return hits


def _extract_amount(text):
    """Fallback: largest currency-marked amount in the text (e.g. SGD 5,000 / $12k)."""
    best = None
    for m in re.finditer(r"(?:S\$|SGD|\$)\s?([\d,]+(?:\.\d+)?)\s?(k|m)?\b", text, re.IGNORECASE):
        value = float(m.group(1).replace(",", "") or 0)
        value *= {"k": 1_000, "m": 1_000_000}.get((m.group(2) or "").lower(), 1)
        best = max(best or 0, value)
    return best


def _band(value, bands):
    for name, minimum in sorted(bands.items(), key=lambda kv: -kv[1]):
        if value >= minimum:
            return name
    return "Low"


def _dedupe(items):
    return list(dict.fromkeys(items))


def triage(summary, amount=None, claim_type=None, config=None):
    cfg = config or load_config()
    text = " ".join((summary or "").split())
    if amount is None:
        amount = _extract_amount(text)

    urgency = _detect(text, cfg["urgency_signals"], negation_aware=True)
    severity = _detect(text, cfg["severity_signals"], negation_aware=True)
    fraud = _detect(text, cfg["fraud_indicators"], negation_aware=False)

    word_count = len(text.split())
    if word_count < cfg["min_words"]:
        fraud.append({**cfg["insufficient_detail"], "evidence": text or "(empty summary)"})

    risk = urgency + severity
    amount_points, amount_label = 0, None
    if amount:
        for band in sorted(cfg["amount_bands"], key=lambda b: -b["min"]):
            if amount >= band["min"]:
                amount_points, amount_label = band["points"], band["label"]
                break
    if amount_points:
        risk.append({"key": "claim_amount", "label": f"{amount_label.capitalize()} claim amount",
                     "weight": amount_points, "evidence": f"Claimed amount: SGD {amount:,.0f}", "actions": []})

    # ---- scoring -----------------------------------------------------------
    fraud_score = min(100, sum(h["weight"] for h in fraud))
    score = min(100, round(sum(h["weight"] for h in risk) + fraud_score * cfg["fraud_priority_weight"]))
    priority_idx = PRIORITY_ORDER.index(_band(score, cfg["priority_bands"]))
    floors = [PRIORITY_ORDER.index(h["priority_floor"]) for h in risk + fraud if h.get("priority_floor")]
    priority = PRIORITY_ORDER[max([priority_idx] + floors)]

    # ---- escalation --------------------------------------------------------
    escalations = []  # (reason, route)
    if priority == "Critical":
        escalations.append(("Critical priority claim", "Senior claims manager"))
    if fraud_score >= cfg["fraud_escalation_score"]:
        escalations.append((f"Fraud indicator score {fraud_score} meets the threshold of {cfg['fraud_escalation_score']}",
                            "Special Investigations Unit (SIU)"))
    for h in risk:
        if h.get("escalate_to"):
            escalations.append((f"{h['label']} detected", h["escalate_to"]))
    if amount and amount >= cfg["large_amount_sgd"]:
        escalations.append((f"Claim amount SGD {amount:,.0f} exceeds SGD {cfg['large_amount_sgd']:,.0f}",
                            "Senior claims manager"))

    # ---- actions and rationale --------------------------------------------
    actions = [f"Escalate to {route}" for route in _dedupe(r for _, r in escalations)]
    actions += cfg["baseline_actions"][priority]
    for h in sorted(fraud + risk, key=lambda h: -h["weight"]):
        actions += h.get("actions", [])

    drivers = [h["label"] for h in sorted(risk, key=lambda h: -h["weight"])][:3]
    rationale = f"{priority} priority (score {score}/100)"
    rationale += f", driven by: {', '.join(drivers)}" if drivers else ", no urgency or severity signals found"
    rationale += f"; {len(fraud)} fraud indicator(s) raised" if fraud else ""
    rationale += ". Escalation recommended." if escalations else ". No escalation needed."

    return {
        "priority": priority,
        "score": score,
        "fraud_score": fraud_score,
        "risk_factors": [{"flag": h["key"], "label": h["label"], "evidence": h["evidence"]} for h in risk],
        "fraud_indicators": [{"flag": h["key"], "label": h["label"], "evidence": h["evidence"]} for h in fraud],
        "recommended_actions": _dedupe(actions),
        "escalate": bool(escalations),
        "escalation_reason": "; ".join(_dedupe(r for r, _ in escalations)) or None,
        "escalation_routes": _dedupe(r for _, r in escalations),
        "rationale": rationale,
        "amount_sgd": amount,
        "claim_type": claim_type,
    }


def _demo():
    data = Path(__file__).resolve().parent.parent / "data" / "mock_claims.json"
    for c in json.loads(data.read_text(encoding="utf-8")):
        r = triage(c["summary"], c["amount_sgd"], c["claim_type"])
        print(f"{c['id']}  {r['priority']:<8} score={r['score']:>3}  fraud={r['fraud_score']:>3}  "
              f"escalate={str(r['escalate']):<5}  {c['label']}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(triage(" ".join(sys.argv[1:])), indent=2))
    else:
        _demo()
