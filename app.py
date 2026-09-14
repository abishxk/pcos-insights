# -*- coding: utf-8 -*-
"""Flask app: PCOS symptom self-check.

Serves a single page (``templates/index.html``) and one JSON endpoint,
``POST /api/predict``, backed by the symptom-only KNN from
:mod:`pcos.symptom_model`.

Run:
    python -m pcos.symptom_model   # once, to train + save the model
    python app.py                  # then open http://127.0.0.1:5000
"""

from __future__ import annotations

import json
import os

import joblib
import pandas as pd
from flask import Flask, jsonify, render_template, request

from pcos.symptom_model import META_PATH, MODEL_PATH, train_and_save

app = Flask(__name__)

if not (os.path.exists(MODEL_PATH) and os.path.exists(META_PATH)):
    train_and_save()

MODEL = joblib.load(MODEL_PATH)
with open(META_PATH, encoding="utf-8") as fh:
    META = json.load(fh)

# form field id -> raw dataframe column
FIELD_TO_COLUMN = {f["field"]: f["column"] for f in META["fields"]}


def _band(probability: float) -> str:
    if probability < 0.34:
        return "lower"
    if probability < 0.6:
        return "moderate"
    return "higher"


# Yes answers we surface as "associated with PCOS". Regular exercise is
# excluded on purpose: in the data it trends mildly protective, so listing it
# as a PCOS-linked factor would be misleading.
FACTOR_LABELS = {
    "Weight gain(Y/N)": "Recent weight gain",
    "hair growth(Y/N)": "Excess hair growth",
    "Skin darkening (Y/N)": "Skin darkening",
    "Hair loss(Y/N)": "Hair thinning or loss",
    "Pimples(Y/N)": "Acne or pimples",
    "Fast food (Y/N)": "Frequent fast food",
}


def _signal_rows() -> list[dict]:
    """Symptoms ordered by how strongly they track PCOS in the data.

    Used to fill the "Strongest signals in this data" panel. Regular exercise
    is left out for the same reason as in the factors list (protective, not a
    PCOS marker) since it shares FACTOR_LABELS.
    """
    assoc = META["symptom_association"]
    rows = [
        {"label": label, "lift": assoc[col]["lift"]}
        for col, label in FACTOR_LABELS.items()
        if col in assoc
    ]
    rows.sort(key=lambda r: r["lift"], reverse=True)
    top = rows[0]["lift"] if rows else 1.0
    for r in rows:
        r["width"] = round(r["lift"] / top * 100)
    return rows


def _contributing_factors(answers: dict) -> list[dict]:
    """Which of the user's yes answers are most associated with PCOS in the data."""
    assoc = META["symptom_association"]
    factors = []
    for col, label in FACTOR_LABELS.items():
        stats = assoc.get(col)
        if stats and answers.get(col) == 1 and stats["lift"] >= 1.2:
            factors.append(
                {
                    "label": label,
                    "lift": stats["lift"],
                    "pcos_rate": stats["pcos_given_symptom"],
                }
            )
    factors.sort(key=lambda f: f["lift"], reverse=True)
    return factors[:4]


def _parse_payload(payload: dict) -> dict:
    """Turn the JSON form payload into {raw column: numeric value}."""
    def num(key, lo, hi):
        raw = payload.get(key, "")
        if raw in (None, ""):
            raise ValueError(f"Please enter your {key.replace('_', ' ')}.")
        try:
            val = float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"'{raw}' is not a valid number for {key.replace('_', ' ')}.")
        if not (lo <= val <= hi):
            raise ValueError(f"{key.replace('_', ' ').capitalize()} should be between {lo} and {hi}.")
        return val

    age = num("age", 12, 70)
    height = num("height_cm", 120, 210)
    weight = num("weight_kg", 25, 200)
    cycle_length = num("cycle_length", 0, 20)
    bmi = round(weight / ((height / 100) ** 2), 2)

    # cycle: front end sends "regular" / "irregular"
    cycle_raw = str(payload.get("cycle_irregular", "")).lower()
    if cycle_raw not in ("regular", "irregular"):
        raise ValueError("Please choose whether your cycle is regular or irregular.")
    cycle_code = 2 if cycle_raw == "regular" else 4

    row = {
        "Age (yrs)": age,
        "Height(Cm)": height,
        "Weight (Kg)": weight,
        "BMI": bmi,
        "Cycle(R/I)": cycle_code,
        "Cycle length(days)": cycle_length,
    }
    for col in META["binary_columns"]:
        fid = next(f["field"] for f in META["fields"] if f["column"] == col)
        row[col] = 1 if payload.get(fid) in (True, "true", "on", 1, "1", "yes") else 0
    return row, bmi


def _base_rate() -> int:
    return round(META["class_balance"]["pcos"] / META["n_samples"] * 100)


@app.get("/")
def landing():
    return render_template("landing.html", active_nav="home")


@app.get("/app")
def symptom_check():
    return render_template(
        "index.html",
        meta=META,
        signals=_signal_rows(),
        base_rate=_base_rate(),
        active_nav="tool",
    )


@app.get("/data")
def data_page():
    return render_template("data.html", meta=META, base_rate=_base_rate(), active_nav="about")


@app.post("/api/predict")
def predict():
    payload = request.get_json(silent=True) or {}
    try:
        row, bmi = _parse_payload(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    frame = pd.DataFrame([[row[c] for c in META["feature_columns"]]],
                         columns=META["feature_columns"])
    probability = float(MODEL.predict_proba(frame)[0, 1])

    # KNN vote share can hit exactly 0 or 1 when every neighbour agrees.
    # A screening estimate should not read as an absolute, so clamp the
    # displayed figure while keeping the raw value available.
    display = min(0.99, max(0.01, probability))

    baseline = META["class_balance"]["pcos"] / META["n_samples"] * 100

    return jsonify(
        {
            "probability": round(probability, 4),
            "percent": round(display * 100, 1),
            "band": _band(probability),
            "baseline_percent": round(baseline),
            "neighbours": META["best_params"]["n_neighbors"],
            "bmi": bmi,
            "factors": _contributing_factors(row),
            "model": {
                "name": "K-Nearest Neighbours",
                "neighbors": META["best_params"]["n_neighbors"],
                "accuracy": META["metrics"]["test_accuracy"],
                "roc_auc": META["metrics"]["test_roc_auc"],
                "n_samples": META["n_samples"],
            },
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
