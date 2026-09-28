# Claims Triage — Flask Demo

A self-contained insurance claims triage web app. Paste a claim summary, optionally pick a claim type and amount band, and get back a structured fraud + urgency score with recommended actions.

No API keys required — the scoring engine is fully rule-based and deterministic.

---

## Prerequisites

- Python 3.9 or later

## Quick start

```bash
cd claims-triage
pip install -r requirements.txt
flask --app wsgi run
```

Then open [http://localhost:5000](http://localhost:5000).

## Configuration (optional)

Copy `.env.example` to `.env` and set:

| Variable | Default | Purpose |
|---|---|---|
| `FLASK_SECRET_KEY` | `dev-secret-key` | Flask session signing key |
| `DATABASE_PATH` | `claims.db` | Path to the SQLite database file |

Flask will pick up `.env` automatically if you have `python-dotenv` installed (`pip install python-dotenv`).

## Project layout

```
claims-triage/
├── app/                    # Flask application package
│   ├── __init__.py         # App factory (create_app)
│   ├── db.py               # SQLite layer
│   ├── routes.py           # Blueprint: /, /score, /result/<id>, /history
│   ├── static/style.css    # Extra styles (Bootstrap 5 via CDN)
│   └── templates/          # Jinja2 templates
│       ├── base.html
│       ├── index.html
│       ├── result.html
│       └── history.html
├── data/
│   └── mock_claims.json    # 6 demo scenarios for the engine test suite
├── tests/
│   └── test_engine.py      # pytest suite for the triage engine
├── triage/
│   ├── engine.py           # Deterministic scoring engine
│   └── config.json         # All rules, weights and thresholds
├── wsgi.py                 # Flask entry point
├── requirements.txt
└── .env.example
```

## Running the engine tests

```bash
cd claims-triage
pip install pytest
pytest tests/
```

## Demo claims

The `data/mock_claims.json` file contains 6 ready-made scenarios covering every priority band:

| ID | Label | Expected priority |
|---|---|---|
| CLM-001 | Routine windscreen chip | Low |
| CLM-002 | Urgent burst pipe | High |
| CLM-003 | Commercial fire + 6 fraud flags | High + Escalate |
| CLM-004 | Serious injury + litigation (SGD 850k) | Critical + Escalate |
| CLM-005 | Vague 3-word submission | Medium |
| CLM-006 | Overseas medical + pre-existing condition | High + Escalate |
